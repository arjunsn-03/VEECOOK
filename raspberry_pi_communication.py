import requests
import json
import logging

class RaspberryPiCommunicator:
    def __init__(self, pi_ip, port=5001):  
        self.pi_base_url = f"http://{pi_ip}:{port}"
        self.logger = logging.getLogger(__name__)

    def send_recipe_start(self, recipe_name, recipe_data):
        try:
            # Add validation for recipe_data
            if not recipe_data or "steps" not in recipe_data:
                return False, "Invalid recipe data"
            
            self.logger.info(f"Sending recipe data: {recipe_data}")
            response = requests.post(
                f"{self.pi_base_url}/start_recipe",
                json={
                    "recipe_name": recipe_name,
                    "steps": recipe_data["steps"]
                },
                timeout=5
            )
            self.logger.info(f"Response from server: {response.text}")
            if response.status_code == 200:
                return True, "Recipe started successfully"
            return False, f"Failed to start recipe: {response.text}"
        except requests.exceptions.ConnectionError:
            return False, "Failed to connect to Raspberry Pi. Please check the server."
        except Exception as e:
            self.logger.error(f"Error sending recipe to Pi: {str(e)}")
            return False, str(e)

    def send_recipe_schedule(self, recipe_name, recipe_data, schedule_time):
        """Send scheduled recipe data to Raspberry Pi"""
        try:
            response = requests.post(
                f"{self.pi_base_url}/schedule_recipe",
                json={
                    "recipe_name": recipe_name,
                    "steps": recipe_data["steps"],
                    "schedule_time": schedule_time.isoformat()
                },
                timeout=5
            )
            if response.status_code == 200:
                return True, "Recipe scheduled successfully"
            return False, f"Failed to schedule recipe: {response.text}"
        except Exception as e:
            self.logger.error(f"Error scheduling recipe on Pi: {str(e)}")
            return False, str(e)

    def get_status(self):
        """Get current status from Raspberry Pi"""
        try:
            response = requests.get(f"{self.pi_base_url}/status", timeout=5)
            if response.status_code == 200:
                return True, response.json()
            return False, "Failed to get status"
        except Exception as e:
            self.logger.error(f"Error getting status from Pi: {str(e)}")
            return False, str(e)

    def abort_recipe(self):
        """Send abort command to Raspberry Pi"""
        try:
            self.logger.info(f"Sending abort request to {self.pi_base_url}/abort_recipe")
            response = requests.post(
                f"{self.pi_base_url}/abort_recipe",
                timeout=5
            )
            self.logger.info(f"Received response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                return True, "Recipe aborted successfully"
            elif response.status_code == 404:
                return False, "Could not connect to the Raspberry Pi server. Please check if it's running."
            else:
                return False, f"Server error: {response.text}"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to the Raspberry Pi. Please check the IP address and network connection."
        except requests.exceptions.Timeout:
            return False, "Connection to Raspberry Pi timed out. Please check the network."
        except Exception as e:
            self.logger.error(f"Error aborting recipe: {str(e)}")
            return False, "An unexpected error occurred. Please check the server logs."