from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from datetime import datetime, timedelta
import time

# ✅ Supabase Credentials
SUPABASE_URL = "https://rjuptubeqliyqbgixmgu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqdXB0dWJlcWxpeXFiZ2l4bWd1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDEwNzU5MDgsImV4cCI6MjA1NjY1MTkwOH0._PR0pz-YX5I1nTXcrTRfFrnuqbIiIPEdbGaJjZnHHok"

# ✅ Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ✅ Ingredients and Recipes
ingredients = {
    "chilli": 50, "turmeric": 100, "salt": 200, "carrot": 5,
    "green_peas": 150, "corn_flour": 300, "oil": 500, "water": 1000
}

recipes = {
    "veg_soup": {
        "ingredients": {"carrot": 2, "green_peas": 50, "corn_flour": 20, "salt": 10, "water": 500},
        "steps": [{"ingredient": "water", "time": 0}, {"ingredient": "carrot", "time": 4}],
        "cooking_time": 20, "description": "A healthy soup.", "veg": True, "calories": 150
    },
    "spicy_soup": {
        "ingredients": {"chilli": 10, "turmeric": 5, "salt": 10, "carrot": 1, "water": 500},
        "steps": [{"ingredient": "carrot", "time": 0}, {"ingredient": "chilli", "time": 5}],
        "cooking_time": 20, "description": "A spicy soup.", "veg": True, "calories": 200
    }
}

scheduled_recipes = {}
ongoing_recipes = {}

# Add these helper functions before the routes
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
        del ongoing_recipes[recipe]
        flash(f"Cooking for {recipe} has been aborted.", "success")
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
            flash("Load ingredients first.", "error")
            return redirect(url_for("choose_recipe"))

    return render_template("start_cooking.html", recipe=recipes[recipe], recipe_name=recipe)

@app.route("/cooking_schedule/<recipe>", methods=["GET", "POST"])
def cooking_schedule(recipe):
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "start_now":
            # Check for ongoing recipe before starting
            ongoing_recipe = get_ongoing_recipe()
            if ongoing_recipe:
                flash(f"Cannot start now. There is an ongoing recipe: {ongoing_recipe}. Please schedule this recipe for later.", "warning")
                return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=True)
            
            ongoing_recipes[recipe] = {
                "start_time": datetime.now(),
                "cooking_time": recipes[recipe]["cooking_time"]
            }
            flash(f"Cooking for {recipe} has started.", "success")
            return redirect(url_for("cooking_status", recipe=recipe, start_time="now"))
        elif action == "schedule_later":
            schedule_time = request.form.get("schedule_time")
            if schedule_time:
                # Create a unique key using recipe name and timestamp
                schedule_key = f"{recipe}_{int(time.time())}"
                scheduled_recipes[schedule_key] = {
                    "recipe_name": recipe,
                    "start_time": schedule_time
                }
                # Format the date and time
                schedule_datetime = datetime.strptime(schedule_time, "%Y-%m-%dT%H:%M")
                formatted_date = schedule_datetime.strftime("%Y-%m-%d")
                formatted_time = schedule_datetime.strftime("%H:%M")
                flash(f"Cooking for {recipe} is scheduled to start at: {formatted_date} at time {formatted_time}.", "success")
                return redirect(url_for("cooking_status", recipe=recipe, start_time=schedule_time))
            else:
                flash("Please enter a valid time.", "error")
                return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=bool(get_ongoing_recipe()))

    # For GET requests, check ongoing recipe
    ongoing_recipe = get_ongoing_recipe()
    return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe, has_ongoing_recipe=bool(ongoing_recipe))

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

    return render_template("cooking_status.html", recipe=recipes[recipe], recipe_name=recipe, start_time=start_time)

@app.route("/get_remaining_time/<recipe>")
def get_remaining_time(recipe):
    if recipe in ongoing_recipes:
        start_time = ongoing_recipes[recipe]["start_time"]
        cooking_time = ongoing_recipes[recipe]["cooking_time"]
        elapsed_time = (datetime.now() - start_time).total_seconds()
        remaining_time = max(cooking_time * 60 - elapsed_time, 0)
        return jsonify({"remaining_time": int(remaining_time)})
    return jsonify({"remaining_time": 0})

# ✅ Register User
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

# ✅ Login User
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

# ✅ Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))

# ✅ Home Page
@app.route("/")
def home():
    return render_template("home.html")

# ✅ Main Page (After Login)
@app.route("/main")
def main():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("login"))
    return render_template("main.html")

# ✅ Choose Recipe
@app.route("/choose_recipe")
def choose_recipe():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))
    return render_template("choose_recipe.html", recipes=recipes)

# ✅ Update Ingredients
@app.route("/update_ingredients", methods=["GET", "POST"])
def update_ingredients():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))
    if request.method == "POST":
        for ingredient in ingredients:
            ingredients[ingredient] = int(request.form.get(ingredient, 0))
        flash("Ingredients updated!", "success")
        return redirect(url_for("choose_recipe"))
    return render_template("update_ingredients.html", ingredients=ingredients)

# ✅ Food Info
@app.route("/food_info")
def food_info():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))
    return render_template("food_info.html")

# ✅ Recipe Status
@app.route("/recipe_status")
def recipe_status():
    if not session.get("logged_in"):
        flash("Please login first.", "error")
        return redirect(url_for("home"))

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

    return render_template("recipe_status.html", 
                         scheduled_recipes=sorted_schedules,
                         ongoing_recipes=valid_ongoing,
                         recipes=recipes)

# ✅ Profile Page
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

# ✅ Run the Flask App
if __name__ == "__main__":
    app.run(debug=True)