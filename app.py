from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import time  # ✅ Fix: Import time module

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session management

# Mock data for ingredients and recipes
ingredients = {
    "chilli": 50,  # in grams
    "turmeric": 100,
    "salt": 200,
    "carrot": 5,  # in units
    "green_peas": 150,  # in grams
    "corn_flour": 300,
    "oil": 500,
    "water": 1000  # in ml
}

recipes = {
    "veg_soup": {
        "ingredients": {
            "carrot": 2,  # 2 units
            "green_peas": 50,  # 50 grams
            "corn_flour": 20,
            "salt": 10,
            "water": 500
        },
        "steps": [
            {"ingredient": "water", "time": 0},
            {"ingredient": "carrot", "time": 4},
            {"ingredient": "green_peas", "time": 3},
            {"ingredient": "corn_flour", "time": 10},
            {"ingredient": "salt", "time": 12}
        ],
        "cooking_time": 20,  # in minutes
        "description": "A healthy and delicious vegetable soup.",
        "veg": True,
        "allergens": "None",
        "calories": 150
    },
    "spicy_soup": {
        "ingredients": {
            "chilli": 10,
            "turmeric": 5,
            "salt": 10,
            "carrot": 1,
            "water": 500
        },
        "steps": [
            {"ingredient": "carrot", "time": 0},
            {"ingredient": "chilli", "time": 5},
            {"ingredient": "turmeric", "time": 10},
            {"ingredient": "salt", "time": 15}
        ],
        "cooking_time": 20,
        "description": "A spicy and flavorful soup for those who love heat.",
        "veg": True,
        "allergens": "None",
        "calories": 200
    }
}

# Mock user database
users = {
    "user1": {
        "password": generate_password_hash("password1"),
        "name": "John Doe",
        "email": "john.doe@example.com",
        "profile_picture": "default.jpg",
        "phone": "",
        "address": "",
        "diet_type": "",
        "allergies": "",
        "preferred_cuisines": "",
        "disliked_ingredients": "",
        "spice_level": "",
        "cooking_time_preference": "",
        "favorite_ingredients": "",
        "auto_suggestions": "Off",
        "connected_machine": "",
        "ingredient_availability": "",
        "preferred_cooking_mode": "",
        "caloric_intake_goal": "",
        "health_goals": "",
        "meal_history": [],
        "favorite_recipes": [],
        "language_preference": "English",
        "notification_preferences": "On",
        "subscription_status": "Free",
        "linked_accounts": [],
        "voice_assistant_integration": "Off",
        "recipe_sharing_preferences": "Private",
        "family_mode": "Off"
    }
}

# Global variables for scheduled and ongoing recipes
scheduled_recipes = {
    "veg_soup": {"start_time": "14:30"},
    "spicy_soup": {"start_time": "15:00"}
}

ongoing_recipes = {
    "veg_soup": {"time_remaining": 10}
}

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # ✅ Ensure username exists in users dictionary
        if username not in users:
            # flash("Invalid username or password!", "error")
            return redirect(url_for("login"))

        # ✅ Ensure "password" key exists
        if "password" not in users[username]:
            #flash("Invalid username or password!", "error")
            return redirect(url_for("login"))

        # ✅ Now check password safely
        if check_password_hash(users[username]["password"], password):
            session["logged_in"] = True
            session["username"] = username
            flash("Login successful!", "success")
            return redirect(url_for("main"))
        else:
           #u flash("Invalid username or password!", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        name = request.form.get("name")
        email = request.form.get("email")
        
        if username in users:
            flash("Username already exists", "error")
            return redirect(url_for("register"))
        
        # Hash the password before storing it
        hashed_password = generate_password_hash(password)
        
        users[username] = {
            "password": hashed_password,
            "name": name,
            "email": email,
        }
        
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html")

@app.route("/main")
def main():
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    return render_template("main.html")

@app.route("/choose_recipe")
def choose_recipe():
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    return render_template("choose_recipe.html", recipes=recipes)

@app.route("/update_ingredients", methods=["GET", "POST"])
def update_ingredients():
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    if request.method == "POST":
        for ingredient in ingredients:
            ingredients[ingredient] = int(request.form.get(ingredient, 0))
        flash("Ingredients updated successfully!", "success")
        return redirect(url_for("choose_recipe"))
    return render_template("update_ingredients.html", ingredients=ingredients)

@app.route("/start_cooking/<recipe>", methods=["GET", "POST"])
def start_cooking(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    
    if request.method == "POST":
        confirmation = request.form.get("confirmation")
        if confirmation == "yes":
            return redirect(url_for("cooking_schedule", recipe=recipe))
        else:
            flash("Please ensure all ingredients are loaded correctly", "error")
            return redirect(url_for("choose_recipe"))
    
    # Pass the recipe details and scheduled_recipes to the template
    return render_template("start_cooking.html", recipe=recipes[recipe], recipe_name=recipe, scheduled_recipes=scheduled_recipes)

@app.route("/cooking_schedule/<recipe>")
def cooking_schedule(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    return render_template("cooking_schedule.html", recipe=recipes[recipe], recipe_name=recipe)

ongoing_recipes = {}  # Stores active timers

@app.route("/cooking_status/<recipe>")
def cooking_status(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))

    start_time = request.args.get("start_time", "now")
    
    if start_time == "now":
        # If cooking starts now, initialize the timer
        if recipe not in ongoing_recipes:  # Prevent overwriting if already cooking
            ongoing_recipes[recipe] = {
                "time_remaining": recipes[recipe]["cooking_time"] * 60,  # Convert to seconds
                "start_timestamp": int(time.time())  # Store start time
            }
    else:
        # If scheduled for later, add it to scheduled_recipes
        scheduled_recipes[recipe] = {"start_time": start_time}
    
    return render_template("cooking_status.html", recipe=recipes[recipe], recipe_name=recipe, start_time=start_time)

@app.route("/get_remaining_time/<recipe>")
def get_remaining_time(recipe):
    if recipe in ongoing_recipes:
        elapsed_time = int(time.time()) - ongoing_recipes[recipe]["start_timestamp"]
        remaining_time = max(ongoing_recipes[recipe]["time_remaining"] - elapsed_time, 0)
        return jsonify({"remaining_time": remaining_time})
    return jsonify({"remaining_time": 0})

@app.route("/abort_cooking/<recipe>")
def abort_cooking(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    
    # Remove the recipe from scheduled or ongoing recipes
    if recipe in scheduled_recipes:
        del scheduled_recipes[recipe]
        flash(f"Aborted scheduled cooking for {recipe}", "success")
    elif recipe in ongoing_recipes:
        del ongoing_recipes[recipe]
        flash(f"Aborted ongoing cooking for {recipe}", "success")
    else:
        flash(f"No active or scheduled cooking found for {recipe}", "error")
    
    return redirect(url_for("recipe_status"))

@app.route("/cooking_completed/<recipe>")
def cooking_completed(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    return render_template("cooking_completed.html", recipe_name=recipe)

@app.route("/food_info")
def food_info():
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    return render_template("food_info.html")

@app.route("/recipe_status")
def recipe_status():
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))
    
    # Pass the variables to the template
    return render_template("recipe_status.html", scheduled_recipes=scheduled_recipes, ongoing_recipes=ongoing_recipes)

@app.route("/edit_schedule/<recipe>", methods=["GET", "POST"])
def edit_schedule(recipe):
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        new_time = request.form.get("new_time")
        if new_time:
            scheduled_recipes[recipe]["start_time"] = new_time
            flash(f"Updated {recipe} to start at {new_time}", "success")
            return redirect(url_for("cooking_status", recipe=recipe, start_time=new_time))
    
    return render_template("edit_schedule.html", recipe_name=recipe)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("logged_in"):
        flash("Please login to access this page", "error")
        return redirect(url_for("home"))

    username = session.get("username")
    user = users.get(username, {})  # Ensure user exists, or use empty dict

    if request.method == "POST":
        # ✅ Use `.get()` to prevent KeyError if the key doesn't exist
        user["name"] = request.form.get("name", user.get("name", ""))
        user["email"] = request.form.get("email", user.get("email", ""))
        user["phone"] = request.form.get("phone", user.get("phone", ""))  # ✅ Fix KeyError here
        user["address"] = request.form.get("address", user.get("address", ""))
        user["diet_type"] = request.form.get("diet_type", user.get("diet_type", "Vegetarian"))
        user["allergies"] = request.form.get("allergies", user.get("allergies", ""))
        user["preferred_cuisines"] = request.form.get("preferred_cuisines", user.get("preferred_cuisines", ""))
        user["disliked_ingredients"] = request.form.get("disliked_ingredients", user.get("disliked_ingredients", ""))
        user["spice_level"] = request.form.get("spice_level", user.get("spice_level", "Medium"))
        user["cooking_time_preference"] = request.form.get("cooking_time_preference", user.get("cooking_time_preference", "Quick Meals"))
        user["favorite_ingredients"] = request.form.get("favorite_ingredients", user.get("favorite_ingredients", ""))
        user["auto_suggestions"] = request.form.get("auto_suggestions") == "on"  # ✅ Convert checkbox to boolean
        user["connected_machine"] = request.form.get("connected_machine", user.get("connected_machine", ""))
        user["ingredient_availability"] = request.form.get("ingredient_availability", user.get("ingredient_availability", ""))
        user["preferred_cooking_mode"] = request.form.get("preferred_cooking_mode", user.get("preferred_cooking_mode", "Manual"))
        user["caloric_intake_goal"] = request.form.get("caloric_intake_goal", user.get("caloric_intake_goal", ""))
        user["health_goals"] = request.form.get("health_goals", user.get("health_goals", ""))
        user["language_preference"] = request.form.get("language_preference", user.get("language_preference", "English"))
        user["notification_preferences"] = request.form.get("notification_preferences", user.get("notification_preferences", ""))
        user["subscription_status"] = request.form.get("subscription_status", user.get("subscription_status", ""))
        user["voice_assistant_integration"] = request.form.get("voice_assistant_integration") == "on"
        user["recipe_sharing_preferences"] = request.form.get("recipe_sharing_preferences", user.get("recipe_sharing_preferences", ""))
        user["family_mode"] = request.form.get("family_mode") == "on"

        # ✅ Update user in the users dictionary
        users[username] = user

        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)