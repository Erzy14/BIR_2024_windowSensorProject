from radio_handle import *
import argparse
import threading
import time
import random
from Crypto.Cipher import AES

RADIO_MODE = RadioMode.FSK # Set the radio modulation: RadioMode.LORA or RadioMode.FSK
SEND_DELAY = 5  # Delay [s] between sending messages
SEND_MSG = "Hello!"  # Message to send
SEND_MESSAGES = False  # Set to False to only receive messages
allowed_devices = ['01','02','03']

devices = []
node_01_last_message = 0
node_02_last_message = 0
node_03_last_message = 0

decrypt_01_cipher = AES.new(node_01_key, AES.MODE_CBC, iv)
decrypt_02_cipher = AES.new(node_01_key, AES.MODE_CBC, iv)
decrypt_03_cipher = AES.new(node_01_key, AES.MODE_CBC, iv)
iv = 'Secure IV, trust me'
node_01_key = 'ABC'
node_02_key = 'DEF'
node_03_key = 'GHI'
this_gateway_id = '10' #z parametru
response_events = {}
print(f"Broker o ID obszaru: {this_gateway_id} - rozpoczyna pracę.")
# Callback function to handle received data.
# This function will be called every time data is received.
def data_callback(data, rssi=None, index=None):
    global node_01_last_message
    global node_02_last_message
    global node_03_last_message ### Mogą się wysypać
    
    print(f"Received data: {data}")
    msg_len = len(data)
    length_correct = False
    correct_gateway = False
    if msg_len == 10: #(9 znaków, 6 plaintext + 3 szyfrogram + 1 znak końca)
        gateway_id = data[1:3]
        length_correct = True
    if length_correct and gateway_id == this_gateway_id: #Sprawdzamy, czy wiadomość kierowana jest do właściwej bramki
        correct_gateway = True
        node_id = data[3:5]
        ciphered = data[5:8]

    if correct_gateway == True and node_id in allowed_devices:
        message_type = int(data[:1]) #0,3,4
        window = int(data[5:6])
        if message_type == 3 and node_id in devices:
            if window == 0:
                window_state = 'zamknięte'
            if window == 1:
                window_state = 'otwarte'
                
            if node_id == '01':
                message_number = decrypt_01_cipher.decrypt(ciphered)
                if message_number.isdigit() and int(message_number) > node_01_last_message and int(message_number) < node_01_last_message + 5:
                    node_01_last_message = int(message_number)
                    print(f"o:[ID: {node_id}][RSSI: {rssi}] Odebrano wiadomość, okno jest " + window_state)
                    send_signal_received(node_id)  # Sygnalizuje odebranie wiadomości od konkretnego node_id
            elif node_id == '02':
                message_number = decrypt_02_cipher.decrypt(ciphered)
                if message_number.isdigit() and int(message_number) > node_02_last_message and int(message_number) < node_02_last_message + 5:
                    node_02_last_message = int(message_number)
                    print(f"o:[ID: {node_id}][RSSI: {rssi}] Odebrano wiadomość, okno jest " + window_state)
                    send_signal_received(node_id)  # Sygnalizuje odebranie wiadomości od konkretnego node_id
            elif node_id == '03':
                message_number = decrypt_03_cipher.decrypt(ciphered)
                if message_number.isdigit() and int(message_number) > node_03_last_message and int(message_number) < node_03_last_message + 5:
                    node_03_last_message = int(message_number)
                    print(f"o:[ID: {node_id}][RSSI: {rssi}] Odebrano wiadomość, okno jest " + window_state)
                    send_signal_received(node_id)  # Sygnalizuje odebranie wiadomości od konkretnego node_id
            
        if message_type == 0 and node_id not in devices: 
            devices.append(node_id)           
            print(f"o:[ID: {node_id}][RSSI: {rssi}] Zarejestrowano nowy czujnik.")
            response_events[node_id] = threading.Event()  # Inicjalizacja Event dla nowego node_id
            message_thread = threading.Thread(target=cycle_executor, args=(node_id,))
            message_thread.start()


def xor_strings(str1, str2):
    if len(str1) != len(str2):
        raise ValueError("Stringi muszą mieć taką samą długość")

    bytes1 = str1.encode('utf-8')
    bytes2 = str2.encode('utf-8')

    xor_result = bytes(a ^ b for a, b in zip(bytes1, bytes2))

    return xor_result.decode('utf-8', errors='ignore')

def send_signal_received(node_id):
    if node_id in response_events:
        response_events[node_id].set()

def cycle_executor(id):
    failures = 0
    msg_to_send = "1" + this_gateway_id + id
    for i in range(2):
        sleep_time = 2 + random.randint(3,8)
        time.sleep(sleep_time)
        radio_handler.send(msg_to_send)    
    while True:
        wait_time = 30 + random.randint(1, 5)
        time.sleep(wait_time)
        response_events[id].clear() #Rozpoczynamy oczekiwanie na wiadomość
        request = "2" + this_gateway_id + id
        radio_handler.send(request)
        print(f"r:[ID: {id}] Wysyłanie żądania.")

        retries = 0
        while retries < 3:
            time_out = 3 + random.randint(2, 5)
            if response_events[id].wait(timeout=time_out):
                break
            else:
                retries += 1
                if retries < 3:
                    print(f"r:[ID: {id}] Brak odpowiedzi - ponowne wysłanie wiadomości.")
                    radio_handler.send(request)

        # Krok 5: Jeśli po 3 próbach nie ma odpowiedzi, wyświetl alert
        if retries == 3:
            print(f"[ID: {id}] Urządzenie nie odpowiada!")
            failures += 1

        if failures == 3:
            print(f"r:[ID: {id}] Urządzenie nie odpowiada. Sprawdź stan urządzenia, a następnie naciśnij na czujniku przycisk reset.")
            devices.remove(id)
            if id == '01':
                node_01_messages.clear()
            elif id == '02':
                node_02_messages.clear()
            elif id == '03':
                node_03_messages.clear()
            break
    print(f"[ID: {id}] Wątek dla urządzenia został zakończony. Oczekiwanie na ponowną rejestrację urządzenia")


radio_handler = RadioHandler(RADIO_MODE, data_callback)

try:
    while True:
        pass
except KeyboardInterrupt:
    print("Reception stopped.")
finally:
    radio_handler.cleanup()  # Clean up GPIO and close SPI
