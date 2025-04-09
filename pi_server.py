from flask import Flask, request, jsonify
import time
import threading
import json
import logging
from adafruit_servokit import ServoKit
import RPi.GPIO as GPIO  # Add GPIO import for relays

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

        # Initialize GPIO first, before any other GPIO operations
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)  # Set mode once at initialization
        
        try:
            # Initialize servo driver (PCA9685)
            self.kit = ServoKit(channels=16)
            
            # Define servo channels (1-5)
            self.servo_channels = {
                1: {"channel": 0},  # Onion (Channel 0)
                2: {"channel": 1},  # Carrot (Channel 1)
                3: {"channel": 2},  # Peas (Channel 2)
                4: {"channel": 3},  # Spices (Channel 3)
                5: {"channel": 4}    # Salt & Pepper (Channel 4)
            }
            
            # Initialize GPIO for pumps and motor
            GPIO.setwarnings(False)
            
            # Relay pins for pumps
            self.relay_pins = {
                'water': 17,
                'oil': 27
            }
            
            # Induction coil relay pin
            self.induction_pin = 16  # GPIO16 for induction coil relay
            
            # L293D motor control pins - updated for A-side pins
            self.motor_pins = {
                'enable': 18,    # Connect to EN_A
                'input1': 23,    # Connect to A1
                'input2': 24     # Connect to A2
            }
            
            # Initialize relays
            for pin in self.relay_pins.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)  # Ensure pumps are OFF
                time.sleep(0.1)
            
            # Initialize induction coil relay
            GPIO.setup(self.induction_pin, GPIO.OUT)
            GPIO.output(self.induction_pin, GPIO.HIGH)  # Ensure induction coil is OFF
            time.sleep(0.1)
            
            # Initialize motor control pins
            for pin in self.motor_pins.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            
            # Setup PWM for motor speed control
            self.motor_pwm = GPIO.PWM(self.motor_pins['enable'], 100)  # 100 Hz frequency
            self.motor_pwm.start(0)  # Start with 0% duty cycle
            
            logger.info("Hardware initialized successfully")
            
            # Add a safety check to ensure pumps are OFF
            self._verify_pumps_off()
            
            # Initialize all servos to 0 degrees
            for channel_data in self.servo_channels.values():
                self.kit.servo[channel_data["channel"]].angle = 0
                time.sleep(0.1)
            
            logger.info("Servo driver and pumps initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing hardware: {e}")
            raise

    def _verify_pumps_off(self):
        """Verify that all pumps are OFF"""
        for pump_type, pin in self.relay_pins.items():
            current_state = GPIO.input(pin)
            if current_state != GPIO.HIGH:
                logger.warning(f"{pump_type} pump not properly OFF, forcing OFF state")
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(0.1)

    def send_servo_command(self, servo_num, angle):
        """Control servo using servo driver"""
        try:
            if servo_num not in self.servo_channels:
                logger.error(f"Invalid servo number: {servo_num}")
                return False
                
            channel = self.servo_channels[servo_num]["channel"]
            
            # Move to dispense position
            logger.info(f"Moving servo {servo_num} to {angle} degrees")
            self.kit.servo[channel].angle = angle
            time.sleep(1)  # Hold position
            
            # Return to starting position (0 degrees)
            self.kit.servo[channel].angle = 0
            time.sleep(1)  # Allow time for movement
            
            return True
            
        except Exception as e:
            logger.error(f"Error controlling servo: {e}")
            return False

    def control_pump(self, pump_type, duration=5):
        """Control specific pump for specified duration"""
        try:
            if pump_type not in self.relay_pins:
                logger.error(f"Invalid pump type: {pump_type}")
                return False
                
            pin = self.relay_pins[pump_type]
            
            # Force OFF state before starting
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.2)  # Longer delay to ensure relay is settled
            
            logger.info(f"Starting {pump_type} pump for {duration} seconds")
            
            # Turn ON pump
            GPIO.output(pin, GPIO.LOW)
            time.sleep(duration)
            
            # Turn OFF pump with verification
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.2)  # Delay to allow relay to settle
            
            # Verify OFF state
            if GPIO.input(pin) != GPIO.HIGH:
                logger.warning(f"{pump_type} pump not properly OFF, retrying...")
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(0.2)
            
            logger.info(f"{pump_type.title()} pump stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error controlling {pump_type} pump: {e}")
            # Emergency shutdown of the pump
            try:
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(0.2)
            except:
                pass
            return False

    def start_stirring(self, speed=60):
        """Start the stirring motor at specified speed (0-100)"""
        try:
            # Set rotation direction
            GPIO.output(self.motor_pins['input1'], GPIO.HIGH)
            GPIO.output(self.motor_pins['input2'], GPIO.LOW)
            
            # Gradually increase speed for smoother start
            for duty in range(0, speed + 1, 5):
                self.motor_pwm.ChangeDutyCycle(duty)
                time.sleep(0.1)
            
            logger.info(f"Started stirring motor at {speed}% speed")
            return True
        except Exception as e:
            logger.error(f"Error starting stirring motor: {e}")
            self.stop_stirring()
            return False

    def stop_stirring(self):
        """Stop the stirring motor"""
        try:
            # Gradually decrease speed for smoother stop
            try:
                current_duty = self.motor_pwm.get_duty_cycle()
            except:
                # If we can't get current duty cycle, assume it's at max
                current_duty = 40  # This matches our starting speed
            
            # Gradually decrease speed in steps
            for duty in range(current_duty, -1, -5):
                self.motor_pwm.ChangeDutyCycle(duty)
                time.sleep(0.1)
            
            # Ensure motor is fully stopped
            self.motor_pwm.ChangeDutyCycle(0)
            # Set both control pins LOW to prevent any current flow
            GPIO.output(self.motor_pins['input1'], GPIO.LOW)
            GPIO.output(self.motor_pins['input2'], GPIO.LOW)
            # Disable the enable pin
            GPIO.output(self.motor_pins['enable'], GPIO.LOW)
            
            logger.info("Stopped stirring motor")
            return True
        except Exception as e:
            logger.error(f"Error stopping stirring motor: {e}")
            # Emergency stop - force all pins LOW
            try:
                self.motor_pwm.ChangeDutyCycle(0)
                GPIO.output(self.motor_pins['input1'], GPIO.LOW)
                GPIO.output(self.motor_pins['input2'], GPIO.LOW)
                GPIO.output(self.motor_pins['enable'], GPIO.LOW)
            except:
                pass
            return False

    def turn_on_induction(self):
        """Turn on the induction coil"""
        try:
            logger.info("Turning on induction coil")
            GPIO.output(self.induction_pin, GPIO.LOW)  # LOW turns the relay ON
            time.sleep(0.2)  # Allow relay to settle
            
            # Verify ON state
            if GPIO.input(self.induction_pin) != GPIO.LOW:
                logger.warning("Induction coil not properly ON, retrying...")
                GPIO.output(self.induction_pin, GPIO.LOW)
                time.sleep(0.2)
            
            logger.info("Induction coil turned ON")
            return True
        except Exception as e:
            logger.error(f"Error turning on induction coil: {e}")
            return False

    def turn_off_induction(self):
        """Turn off the induction coil"""
        try:
            logger.info("Turning off induction coil")
            GPIO.output(self.induction_pin, GPIO.HIGH)  # HIGH turns the relay OFF
            time.sleep(0.2)  # Allow relay to settle
            
            # Verify OFF state
            if GPIO.input(self.induction_pin) != GPIO.HIGH:
                logger.warning("Induction coil not properly OFF, retrying...")
                GPIO.output(self.induction_pin, GPIO.HIGH)
                time.sleep(0.2)
            
            logger.info("Induction coil turned OFF")
            return True
        except Exception as e:
            logger.error(f"Error turning off induction coil: {e}")
            return False

    def execute_recipe(self, recipe_name, steps):
        """Execute recipe steps"""
        logger.info(f"Starting recipe: {recipe_name}")
        start_time = time.time()

        try:
            # Turn on induction coil at the start of cooking
            logger.info("Turning on induction coil for cooking")
            self.turn_on_induction()
            
            # Start oil pump immediately (0 seconds)
            logger.info("Starting oil pump")
            self.control_pump('oil', 5)  # Run for 5 seconds
            
            # Start stirring motor after 2 seconds
            time.sleep(2)
            self.start_stirring(speed=40)  # Start at 40% speed
            
            # Execute ingredient dispensing steps
            for step in steps:
                if self.abort_flag:
                    logger.info("Recipe aborted")
                    break
                
                current_time = time.time()
                elapsed_time = current_time - start_time
                wait_time = step['time'] - elapsed_time
                
                if wait_time > 0:
                    logger.info(f"Waiting {wait_time:.1f} seconds before {step['ingredient']}")
                    time.sleep(wait_time)
                
                logger.debug(f"Step details: {step}")
                logger.info(f"Elapsed time: {elapsed_time:.2f}s")
                logger.info(f"Processing step: {step['ingredient']}")
                if self.send_servo_command(step['servo'], step['amount']):
                    logger.info(f"Successfully completed: {step['ingredient']}")
                else:
                    logger.error(f"Failed to complete: {step['ingredient']}")
                
                # Add water based on recipe type
                if recipe_name == 'veg_soup' and step['ingredient'] == 'spices':
                    water_time = 25
                elif recipe_name == 'spicy_soup' and step['ingredient'] == 'chilly':
                    water_time = 15
                else:
                    water_time = None
                    
                if water_time:
                    logger.info("Starting water pump")
                    self.control_pump('water', 10)
                
                time.sleep(1)
            
            # After all steps are complete, stop the stirring motor
            logger.info("Recipe steps completed, stopping stirring motor")
            self.stop_stirring()
            
        except Exception as e:
            logger.error(f"Error during recipe execution: {e}")
            self.stop_stirring()
            raise
        finally:
            # Turn off induction coil when recipe is complete or aborted
            logger.info("Turning off induction coil")
            self.turn_off_induction()
            
            self.stop_stirring()
            self.current_recipe = None
            logger.info(f"Recipe {recipe_name} completed")

    def cleanup(self):
        """Cleanup on shutdown"""
        try:
            # Ensure GPIO mode is still set before cleanup
            if GPIO.getmode() != GPIO.BCM:
                GPIO.setmode(GPIO.BCM)

            # Stop motor with extra verification
            self.stop_stirring()
            
            if hasattr(self, 'motor_pwm'):
                self.motor_pwm.ChangeDutyCycle(0)
                self.motor_pwm.stop()
            
            # Set all motor pins LOW
            for pin in self.motor_pins.values():
                if GPIO.getmode() is not None:  # Check if GPIO mode is set
                    GPIO.output(pin, GPIO.LOW)
            
            # Return all servos to 0 degrees
            for channel_data in self.servo_channels.values():
                self.kit.servo[channel_data["channel"]].angle = 0
            
            # Ensure all relays are OFF
            for pin in self.relay_pins.values():
                if GPIO.getmode() is not None:  # Check if GPIO mode is set
                    GPIO.output(pin, GPIO.HIGH)
                    time.sleep(0.2)
            
            # Ensure induction coil is OFF
            if GPIO.getmode() is not None and hasattr(self, 'induction_pin'):
                GPIO.output(self.induction_pin, GPIO.HIGH)
                time.sleep(0.2)
            
            GPIO.cleanup()
            logger.info("Hardware cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            # Emergency shutdown
            try:
                if GPIO.getmode() is not None:
                    GPIO.output(self.motor_pins['enable'], GPIO.LOW)
                    if hasattr(self, 'induction_pin'):
                        GPIO.output(self.induction_pin, GPIO.HIGH)
                GPIO.cleanup()
            except:
                pass

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
            # Turn off induction coil when recipe is aborted
            recipe_manager.turn_off_induction()
            recipe_manager.current_recipe = None
            logger.info("Recipe aborted successfully")
            return jsonify({"message": "Recipe aborted successfully"})
        else:
            logger.info("No recipe in progress to abort")
            return jsonify({"message": "No recipe in progress"})
    except Exception as e:
        logger.error(f"Error aborting recipe: {e}")
        return jsonify({"error": str(e)}), 500

# Cleanup on shutdown
import atexit
atexit.register(recipe_manager.cleanup)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        recipe_manager.cleanup()