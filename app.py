from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from datetime import datetime, timedelta
import time
from raspberry_pi_communication import RaspberryPiCommunicator
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Supabase Credentials
SUPABASE_URL = "https://rjuptubeqliyqbgixmgu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqdXB0dWJlcWxpeXFiZ2l4bWd1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDEwNzU5MDgsImV4cCI6MjA1NjY1MTkwOH0._PR0pz-YX5I1nTXcrTRfFrnuqbIiIPEdbGaJjZnHHok"

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Raspberry Pi Communicator
RASPBERRY_PI_IP = os.getenv('RASPBERRY_PI_IP', '192.168.185.77')  # Make sure this IP is correct
pi_communicator = RaspberryPiCommunicator(RASPBERRY_PI_IP, port=5001)  # Updated port to 5001

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Servo pin configuration
SERVO_PINS = {
    "water": 12,    # GPIO 12 - First servo
    "carrot": 13,   # GPIO 13 - Second servo
    "peas": 18,     # GPIO 18 - Third servo
    "spices": 23,   # GPIO 23 - Fourth servo
    "salt_pepper": 24  # GPIO 24 - Fifth servo
}

# Define recipes with only veg_soup and spicy_soup
recipes = {
    'veg_soup': {
        'description': 'A healthy vegetable soup with mixed vegetables and aromatic spices',
        'cooking_time': 40,  # seconds
        'calories': 120,
        'veg': True,
        'ingredients': {
            'water': {'amount': 500, 'unit': 'ml', 'min_required': 500},
            'oil': {'amount': 30, 'unit': 'ml', 'min_required': 30},
            'onion': {'amount': 100, 'unit': 'g', 'min_required': 100},
            'carrot': {'amount': 100, 'unit': 'g', 'min_required': 100},
            'peas': {'amount': 50, 'unit': 'g', 'min_required': 50},
            'spices': {'amount': 10, 'unit': 'g', 'min_required': 10},
            'salt_and_pepper': {'amount': 5, 'unit': 'g', 'min_required': 5}
        },
        'steps': [
            {'time': 5, 'ingredient': 'onion', 'servo': 1, 'amount': 90},
            {'time': 10, 'ingredient': 'carrot', 'servo': 2, 'amount': 90},
            {'time': 15, 'ingredient': 'peas', 'servo': 3, 'amount': 90},
            {'time': 20, 'ingredient': 'spices', 'servo': 4, 'amount': 90},
            {'time': 25, 'ingredient': 'salt_and_pepper', 'servo': 5, 'amount': 90}
        ]
    },
    'spicy_soup': {
        'description': 'A spicy soup with aromatic chilly',
        'cooking_time': 25,  # seconds
        'calories': 90,
        'veg': True,
        'ingredients': {
            'water': {'amount': 400, 'unit': 'ml', 'min_required': 400},
            'oil': {'amount': 25, 'unit': 'ml', 'min_required': 25},
            'chilly': {'amount': 20, 'unit': 'g', 'min_required': 20}
        },
        'steps': [
            {'time': 5, 'ingredient': 'chilly', 'servo': 1, 'amount': 90}
        ]
    }
}

# Define ingredients with only those needed for veg and spicy soups
ingredients = {
    'water': {'amount': 1000, 'unit': 'ml', 'min_required': 500},
    'oil': {'amount': 500, 'unit': 'ml', 'min_required': 200},
    'onion': {'amount': 500, 'unit': 'g', 'min_required': 100},
    'carrot': {'amount': 500, 'unit': 'g', 'min_required': 100},
    'peas': {'amount': 300, 'unit': 'g', 'min_required': 50},
    'spices': {'amount': 100, 'unit': 'g', 'min_required': 10},
    'salt_and_pepper': {'amount': 50, 'unit': 'g', 'min_required': 5},
    'chilly': {'amount': 100, 'unit': 'g', 'min_required': 20}
}

scheduled_recipes = {}
ongoing_recipes = {}
completed_recipes = {}  # New dictionary to store completed recipes

# Helper functions
def has_ongoing_recipe():
    return len(ongoing_recipes) > 0

def get_ongoing_recipe():
    if ongoing_recipes:
        return list(ongoing_recipes.keys())[0]
    return None

def check_schedule_conflict(recipe, start_time):
    if not start_time or start_time == "now":
        start_time = datetime.now()
    else:
        start_time = datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
    
    cooking_time = recipes[recipe]["cooking_time"]
    end_time = start_time + timedelta(minutes=cooking_time)
    
    for scheduled_recipe, schedule_info in scheduled_recipes.items():
        scheduled_start = datetime.strptime(schedule_info["start_time"], "%Y-%m-%dT%H:%M")
        scheduled_end = scheduled_start + timedelta(minutes=recipes[scheduled_recipe]["cooking_time"])
        
        if (start_time <= scheduled_end and end_time >= scheduled_start):
            return scheduled_recipe, schedule_info["start_time"]
    
    return None, None

def check_recipe_completion():
    """Check if any ongoing recipes are completed based on their cooking time"""
    current_time = datetime.now()
    completed = []
    
    for recipe, info in ongoing_recipes.items():
        if recipe not in recipes:
            # Invalid recipe, remove it
            completed.append(recipe)
            continue
            
        start_time = info["start_time"]
        cooking_time = recipes[recipe]["cooking_time"]
        
        # Calculate if recipe is complete
        elapsed_time = (current_time - start_time).total_seconds()
        if elapsed_time >= cooking_time:
            completed.append(recipe)
            
    # Move completed recipes to completed_recipes
    for recipe in completed:
        recipe_info = ongoing_recipes.pop(recipe)
        completed_recipes[recipe] = {
            "start_time": recipe_info["start_time"],
            "completion_time": current_time,
            "cooking_time": recipe_info["cooking_time"]
        }
        logger.info(f"Recipe {recipe} completed and moved to completed_recipes")

@app.route("/edit_schedule/<recipe>", methods=["GET", "POST"])
def edit_schedule(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        new_time = request.form.get("new_time")
        if new_time:
            scheduled_recipes[recipe] = {"start_time": new_time}
            flash(f"Updated {recipe} to start at {new_time}", "success")
            return redirect(url_for("cooking_status", recipe=recipe, start_time=new_time))

    return render_template("edit_schedule.html", recipe_name=recipe)

@app.route("/abort_cooking/<recipe>", methods=["GET", "POST"])
def abort_cooking(recipe):
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    # First check for ongoing recipe
    if recipe in ongoing_recipes:
        # Send abort command to Raspberry Pi
        success, message = pi_communicator.abort_recipe()
        if success:
            del ongoing_recipes[recipe]
            flash(f"Cooking for {recipe} has been aborted.", "success")
        else:
            flash(f"Error aborting recipe: {message}", "error")
        return redirect(url_for("recipe_status"))

    # Then check for scheduled recipe
    for schedule_key, schedule_info in scheduled_recipes.items():
        if schedule_key == recipe:
            recipe_name = schedule_info["recipe_name"]
            del scheduled_recipes[recipe]
            flash(f"Scheduled cooking for {recipe_name} has been cancelled.", "success")
            return redirect(url_for("recipe_status"))

    # If neither found
    flash("Recipe not found.", "error")
    return redirect(url_for("recipe_status"))

@app.route("/start_cooking/<recipe>", methods=["GET", "POST"])
def start_cooking(recipe):
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        confirmation = request.form.get("confirmation")
        if confirmation == "yes":
            return redirect(url_for("cooking_schedule", recipe=recipe))
        else:
            flash("Please load ingredients before proceeding.", "error")
            return redirect(url_for("start_cooking", recipe=recipe))

    # For GET requests, show the ingredients loading page
    if recipe not in recipes:
        flash("Recipe not found.", "error")
        return redirect(url_for("choose_recipe"))
    
    # Pass both recipe and ingredients to the template
    return render_template("start_cooking.html", 
                         recipe=recipes[recipe], 
                         recipe_name=recipe,
                         ingredients=ingredients)

@app.route("/cooking_schedule/<recipe>", methods=["GET", "POST"])
def cooking_schedule(recipe):
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "start_now":
                # Check for ongoing recipe before starting
                ongoing_recipe = get_ongoing_recipe()
                if ongoing_recipe:
                    flash(f"Cannot start now. There is an ongoing recipe: {ongoing_recipe}. Please schedule this recipe for later.", "warning")
                    return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=True)
                
                logger.info(f"Starting recipe: {recipe}")
                # Send recipe to Raspberry Pi with retries
                max_retries = 3
                for attempt in range(max_retries):
                    logger.info(f"Attempt {attempt + 1} to start recipe {recipe}")
                    success, message = pi_communicator.send_recipe_start(recipe, recipes[recipe])
                    if success:
                        ongoing_recipes[recipe] = {
                            "start_time": datetime.now(),
                            "cooking_time": recipes[recipe]["cooking_time"]
                        }
                        flash(f"Cooking for {recipe} has started.", "success")
                        logger.info(f"Successfully started recipe: {recipe}")
                        return redirect(url_for("cooking_status", recipe=recipe, start_time="now"))
                    elif attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {message}. Retrying...")
                        time.sleep(1)  # Wait before retry
                
                # If all retries failed
                error_msg = f"Failed to start recipe: {message}. Please check Arduino connection and try again."
                logger.error(error_msg)
                flash(error_msg, "error")
                return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=False)
                
            elif action == "schedule_later":
                schedule_time = request.form.get("schedule_time")
                if schedule_time:
                    # Send schedule to Raspberry Pi
                    schedule_datetime = datetime.strptime(schedule_time, "%Y-%m-%dT%H:%M")
                    logger.info(f"Scheduling recipe {recipe} for {schedule_datetime}")
                    success, message = pi_communicator.send_recipe_schedule(recipe, recipes[recipe], schedule_datetime)
                    if not success:
                        error_msg = f"Failed to schedule recipe: {message}"
                        logger.error(error_msg)
                        flash(error_msg, "error")
                        return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=bool(get_ongoing_recipe()))
                    
                    # Create a unique key using recipe name and timestamp
                    schedule_key = f"{recipe}_{int(time.time())}"
                    scheduled_recipes[schedule_key] = {
                        "recipe_name": recipe,
                        "start_time": schedule_time
                    }
                    # Format the date and time
                    formatted_date = schedule_datetime.strftime("%Y-%m-%d")
                    formatted_time = schedule_datetime.strftime("%H:%M")
                    success_msg = f"Cooking for {recipe} is scheduled to start at: {formatted_date} at time {formatted_time}."
                    logger.info(success_msg)
                    flash(success_msg, "success")
                    return redirect(url_for("cooking_status", recipe=recipe, start_time=schedule_time))
                else:
                    flash("Please enter a valid time.", "error")
                    return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=bool(get_ongoing_recipe()))

        # For GET requests, check ongoing recipe
        ongoing_recipe = get_ongoing_recipe()
        return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=bool(ongoing_recipe))

    except Exception as e:
        error_msg = f"Error in cooking schedule: {str(e)}"
        logger.error(error_msg)
        flash(error_msg, "error")
        return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=False)

@app.route("/cooking_status/<recipe>")
def cooking_status(recipe):
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    start_time = request.args.get("start_time", "now")
    if start_time == "now":
        ongoing_recipes[recipe] = {
            "start_time": datetime.now(),
            "cooking_time": recipes[recipe]["cooking_time"]
        }
    else:
        scheduled_recipes[recipe] = {
            "start_time": start_time
        }

    # Get Arduino messages from Raspberry Pi
    success, response = pi_communicator.get_status()
    arduino_messages = []
    if success and isinstance(response, dict):
        arduino_messages = response.get("arduino_messages", [])

    return render_template("cooking_status.html", 
                         recipe=recipes[recipe], 
                         recipe_name=recipe, 
                         start_time=start_time,
                         arduino_messages=arduino_messages)

@app.route("/get_remaining_time/<recipe>")
def get_remaining_time(recipe):
    if recipe in ongoing_recipes:
        start_time = ongoing_recipes[recipe]["start_time"]
        cooking_time = recipes[recipe]["cooking_time"]  # This is now in seconds
        elapsed_time = (datetime.now() - start_time).total_seconds()
        remaining_time = max(cooking_time - elapsed_time, 0)
        
        # Automatically move completed recipe to completed_recipes
        if remaining_time <= 0:
            recipe_info = ongoing_recipes.pop(recipe)
            completed_recipes[recipe] = {
                "start_time": recipe_info["start_time"],
                "completion_time": datetime.now(),
                "cooking_time": recipe_info["cooking_time"]
            }
        
        # Get latest Arduino messages
        success, response = pi_communicator.get_status()
        arduino_messages = []
        if success and isinstance(response, dict):
            arduino_messages = response.get("arduino_messages", [])
            
        # Add status message based on time
        if remaining_time > 0:
            if elapsed_time <= 5:
                arduino_messages.append("Water pump active")
            elif 10 <= elapsed_time <= 15:
                arduino_messages.append("Oil pump active")
            
        return jsonify({
            "remaining_time": int(remaining_time),
            "arduino_messages": arduino_messages,
            "current_step": get_current_step(elapsed_time, recipe),
            "is_completed": remaining_time <= 0
        })
    return jsonify({"remaining_time": 0, "arduino_messages": [], "is_completed": True})

def get_current_step(elapsed_time, recipe):
    """Helper function to determine current step based on elapsed time"""
    if elapsed_time <= 5:
        return "Dispensing water"
    elif 10 <= elapsed_time <= 15:
        return "Dispensing oil"
    
    # Check other steps
    for step in recipes[recipe]["steps"]:
        if abs(elapsed_time - step["time"]) < 2:  # Within 2 seconds of the step
            return f"Adding {step['ingredient']}"
    
    return "In progress"

# Register User
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        hashed_password = generate_password_hash(password)

        existing_user = supabase.table("users").select("username").eq("username", username).execute()
        if existing_user.data:
            flash("Username already exists!", "error")
            return redirect(url_for("register"))

        supabase.table("users").insert({
            "full_name": full_name, "username": username, "email": email, "password": hashed_password
        }).execute()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# Login User
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        response = supabase.table("users").select("*").eq("username", username).execute()
        user = response.data

        if not user:
            flash("Invalid username or password!", "error")
            return redirect(url_for("login"))

        user = user[0]
        if check_password_hash(user["password"], password):
            session["logged_in"] = True
            session["username"] = username
            flash("Login successful!", "success")
            return redirect(url_for("main"))
        else:
            flash("Invalid username or password!", "error")
            return redirect(url_for("login"))

    return render_template("login.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))

# Home Page
@app.route("/")
def home():
    return render_template("home.html")

# Main Page (After Login)
@app.route("/main")
def main():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("login"))
    return render_template("main.html")

# Choose Recipe
@app.route("/choose_recipe")
def choose_recipe():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Check ingredients availability for each recipe
    available_recipes = {}
    for recipe_name, recipe in recipes.items():
        if check_recipe_ingredients(recipe):
            available_recipes[recipe_name] = recipe
    
    return render_template('choose_recipe.html', recipes=available_recipes)

def check_recipe_ingredients(recipe):
    for ingredient, data in recipe['ingredients'].items():
        if ingredients[ingredient]['amount'] < data['amount']:
            return False
    return True

@app.route("/update_ingredients", methods=["GET", "POST"])
def update_ingredients():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    if request.method == "POST":
        # Update ingredient amounts
        for ingredient in ingredients.keys():
            amount = request.form.get(ingredient, type=float)
            if amount is not None:
                ingredients[ingredient]['amount'] = amount
        flash('Ingredients updated successfully!', 'success')
        return redirect(url_for('choose_recipe'))
    
    return render_template('update_ingredients.html', ingredients=ingredients)

# Food Info
@app.route("/food_info")
def food_info():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))
    return render_template("food_info.html")

# Recipe Status
@app.route("/recipe_status")
def recipe_status():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    # Check for completed recipes
    check_recipe_completion()

    # Sort scheduled recipes by start time
    sorted_schedules = []
    for recipe_key, schedule_info in scheduled_recipes.items():
        # Get the recipe name, either from schedule_info or from the key
        recipe_name = schedule_info.get('recipe_name', '')
        if not recipe_name and '_' in recipe_key:
            recipe_name = recipe_key.split('_')[0]
        
        # Only add to sorted list if it's a valid recipe
        if recipe_name in recipes:
            sorted_schedules.append({
                'key': recipe_key,
                'recipe_name': recipe_name,
                'start_time': schedule_info['start_time'],
                'cooking_time': recipes[recipe_name]['cooking_time']
            })
    
    # Sort by start time
    sorted_schedules.sort(key=lambda x: datetime.strptime(x['start_time'], "%Y-%m-%dT%H:%M"))

    # Filter ongoing recipes to only include valid ones
    valid_ongoing = {
        recipe: info for recipe, info in ongoing_recipes.items() 
        if recipe in recipes
    }

    # Sort completed recipes by completion time (most recent first)
    sorted_completed = []
    for recipe, info in completed_recipes.items():
        if recipe in recipes:
            sorted_completed.append({
                'recipe_name': recipe,
                'start_time': info['start_time'],
                'completion_time': info['completion_time'],
                'cooking_time': info['cooking_time']
            })
    
    sorted_completed.sort(key=lambda x: x['completion_time'], reverse=True)

    return render_template("recipe_status.html", 
                         scheduled_recipes=sorted_schedules,
                         ongoing_recipes=valid_ongoing,
                         completed_recipes=sorted_completed,
                         recipes=recipes)

# Profile Page
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    username = session.get("username")
    response = supabase.table("users").select("*").eq("username", username).execute()
    user = response.data[0] if response.data else {}

    if request.method == "POST":
        update_data = {
            "full_name": request.form.get("name", user.get("full_name", "")),
            "email": request.form.get("email", user.get("email", ""))
        }
        supabase.table("users").update(update_data).eq("username", username).execute()
        flash("Profile updated!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)

@app.context_processor
def inject_ongoing_recipes():
    return dict(ongoing_recipes=ongoing_recipes)

# Run the Flask App
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
