from flask import Flask, request, jsonify
import RPi.GPIO as GPIO
import time
import threading
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class RecipeManager:
    def __init__(self):
        self.current_recipe = None
        self.abort_flag = False
        
        # GPIO Setup for multiple servos
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Define servo pins
        self.servo_pins = {
            12: {"pin": 12, "pwm": None},  # Water
            13: {"pin": 13, "pwm": None},  # Carrot
            18: {"pin": 18, "pwm": None},  # Peas
            23: {"pin": 23, "pwm": None},  # Spices
            24: {"pin": 24, "pwm": None}   # Salt & Pepper
        }
        
        # Initialize all servos
        for pin_data in self.servo_pins.values():
            GPIO.setup(pin_data["pin"], GPIO.OUT)
            pin_data["pwm"] = GPIO.PWM(pin_data["pin"], 50)  # 50Hz frequency
            pin_data["pwm"].start(self.angle_to_duty_cycle(0))
            time.sleep(0.1)  # Small delay between initializations
            pin_data["pwm"].ChangeDutyCycle(0)
        
        logger.info("All GPIO pins initialized for servo control")

    def angle_to_duty_cycle(self, angle):
        """Convert angle (0-180) to duty cycle (2-12)"""
        return (angle / 18.0) + 2

    def send_servo_command(self, servo_pin, angle):
        """Control servo using GPIO PWM"""
        try:
            if servo_pin not in self.servo_pins:
                logger.error(f"Invalid GPIO pin: {servo_pin}")
                return False
                
            pwm = self.servo_pins[servo_pin]["pwm"]
            
            # Move to dispense position
            duty = self.angle_to_duty_cycle(angle)
            logger.info(f"Moving servo on GPIO {servo_pin} to {angle} degrees (duty cycle: {duty})")
            
            pwm.ChangeDutyCycle(duty)
            time.sleep(1)  # Hold position
            
            # Return to starting position (0 degrees)
            pwm.ChangeDutyCycle(self.angle_to_duty_cycle(0))
            time.sleep(1)  # Allow time for movement
            
            # Stop sending pulses to prevent jitter
            pwm.ChangeDutyCycle(0)
            
            return True
            
        except Exception as e:
            logger.error(f"Error controlling servo: {e}")
            return False

    def execute_recipe(self, recipe_name, steps):
        """Execute recipe steps"""
        logger.info(f"Starting recipe: {recipe_name}")
        start_time = time.time()
        
        for step in steps:
            if self.abort_flag:
                logger.info("Recipe aborted")
                break
                
            # Calculate and wait for the correct timing
            elapsed_time = time.time() - start_time
            wait_time = step['time'] - elapsed_time
            
            if wait_time > 0:
                logger.info(f"Waiting {wait_time:.1f} seconds before {step['ingredient']}")
                time.sleep(wait_time)
            
            # Process the step
            logger.info(f"Processing step: {step['ingredient']}")
            if self.send_servo_command(step['servo'], step['amount']):
                logger.info(f"Successfully completed: {step['ingredient']}")
            else:
                logger.error(f"Failed to complete: {step['ingredient']}")
            
            time.sleep(1)  # Small delay between steps
        
        logger.info(f"Recipe {recipe_name} completed")
        self.current_recipe = None

    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        for pin_data in self.servo_pins.values():
            if pin_data["pwm"]:
                pin_data["pwm"].stop()
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")

# Initialize recipe manager
recipe_manager = RecipeManager()

@app.route('/start_recipe', methods=['POST'])
def start_recipe():
    try:
        data = request.json
        logger.info(f"Received recipe request: {json.dumps(data)}")
        
        if recipe_manager.current_recipe:
            return jsonify({"error": "Recipe already in progress"}), 400
            
        recipe_name = data['recipe_name']
        steps = data['steps']
        
        recipe_manager.current_recipe = recipe_name
        recipe_manager.abort_flag = False
        
        # Start recipe execution in a separate thread
        thread = threading.Thread(
            target=recipe_manager.execute_recipe,
            args=(recipe_name, steps)
        )
        thread.start()
        
        return jsonify({"message": "Recipe started successfully"})
        
    except Exception as e:
        logger.error(f"Error starting recipe: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "current_recipe": recipe_manager.current_recipe
    })

@app.route('/abort_recipe', methods=['POST'])
def abort_recipe():
    try:
        logger.info("Received abort request")
        if recipe_manager.current_recipe:
            recipe_manager.abort_flag = True
            recipe_manager.current_recipe = None
            logger.info("Recipe aborted successfully")
            return jsonify({"message": "Recipe aborted successfully"})
        else:
            logger.info("No recipe in progress to abort")
            return jsonify({"message": "No recipe in progress"})
    except Exception as e:
        logger.error(f"Error aborting recipe: {e}")
        return jsonify({"error": str(e)}), 500

# Cleanup GPIO on shutdown
import atexit
atexit.register(recipe_manager.cleanup)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5001, debug=False)
    finally:
        recipe_manager.cleanup()