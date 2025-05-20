import common_utils
import time
import random
import socket

TIMEOUT = 2
MAX_PAYLOAD_SIZE = 3
WINDOW_SIZE = 4

LOSS_PROBABILITY = 0.2
CORRUPTION_PROBABILITY = 0.1
ACK_LOSS_PROBABILITY = 0.1
ACK_CORRUPTION_PROBABILITY = 0.1
FORCE_LOST = set()
FORCE_CORRUPT = set()

def choose_protocol():
    print("\nEscolha o protocolo de comunicação:")
    print("1 - Go-Back-N")
    print("2 - Repetição Seletiva")
    while True:
        choice = input("Digite sua escolha (1 ou 2): ")
        if choice == '1':
            return "GBN"
        elif choice == '2':
            return "SR"
        else:
            print("Escolha inválida. Digite 1 ou 2.")

def print_window(base, next_seq_num):
    print(f"🪟 Janela atual: {base} - {base + WINDOW_SIZE - 1}")

def start_client(host='localhost', port=12345):
    global FORCE_LOST, FORCE_CORRUPT
    sem_perdas = "True"
    sem_corrupcoes = "True"
    client_socket = common_utils.create_socket()
    if client_socket is None:
        print("Não foi possível criar o socket do cliente.")
        return

    try:
        client_socket.connect((host, port))
        print(f"Conectado ao servidor {host}:{port}")

        protocol = choose_protocol()
        while True:
            message = input("\nDigite a mensagem para enviar (ou 'sair' para terminar): ")
            if message.lower() == 'sair':
                break

            force_lost_input = input("Enter - Simulação com perdas || -1 - Sem perdas || Nºs dos pacotes a perder: ")
            if force_lost_input != "-1":
                FORCE_LOST = set(map(int, force_lost_input.split(','))) if force_lost_input else set()
                sem_perdas = "False"

            force_corrupt_input = input("Enter - Simulação com corrupções || -1 - Sem corrupções || Nºs a corromper: ")
            if force_corrupt_input != "-1":
                FORCE_CORRUPT = set(map(int, force_corrupt_input.split(','))) if force_corrupt_input else set()
                sem_corrupcoes = "False"

            packets = [message[i:i+MAX_PAYLOAD_SIZE] for i in range(0, len(message), MAX_PAYLOAD_SIZE)]
            total_packets = len(packets)

            base = 0
            next_seq_num = 0
            acked = [False] * total_packets
            timers = {}
            client_socket.settimeout(0.5)

            print_window(base, next_seq_num)
            print(f"Simulação sem perdas: {sem_perdas}")
            print(f"Simulação sem corrupções: {sem_corrupcoes}")

            handshake_message = f"PROTOCOLO:{protocol};TAMANHO_JANELA:{WINDOW_SIZE};TAMANHO_PACOTE:{MAX_PAYLOAD_SIZE};sem_perdas:{sem_perdas};sem_corrupções:{sem_corrupcoes}"
            client_socket.sendall(handshake_message.encode())
            server_response = client_socket.recv(1024)
            print(f"Resposta do servidor: {server_response.decode()}")

            while base < total_packets:
                while next_seq_num < base + WINDOW_SIZE and next_seq_num < total_packets:
                    data = packets[next_seq_num]
                    seq = next_seq_num % 256

                    if sem_corrupcoes == "False" and (seq in FORCE_CORRUPT or random.random() < CORRUPTION_PROBABILITY):
                        corrupted_data = "###"
                        packet = common_utils.create_packet(seq, corrupted_data)
                    else:
                        packet = common_utils.create_packet(seq, data)

                    if sem_perdas == "False" and (seq in FORCE_LOST or random.random() < LOSS_PROBABILITY):
                        pass  # pacote perdido
                    else:
                        client_socket.sendall(packet)

                    timers[next_seq_num] = time.time()
                    next_seq_num += 1

                try:
                    response = client_socket.recv(1024)

                    if len(response) != 2:
                        continue

                    if sem_perdas == "False" and random.random() < ACK_LOSS_PROBABILITY:
                        continue
                    if sem_corrupcoes == "False" and random.random() < ACK_CORRUPTION_PROBABILITY:
                        continue

                    if response.startswith(b'N'):
                        nack_seq = common_utils.parse_nack(response)
                        if protocol == "GBN":
                            base = next_seq_num = nack_seq
                            print_window(base, next_seq_num)
                        elif protocol == "SR":
                            for i in range(total_packets):
                                if i % 256 == nack_seq:
                                    packet = common_utils.create_packet(nack_seq, packets[i])
                                    client_socket.sendall(packet)
                                    timers[i] = time.time()
                        continue

                    ack_seq = common_utils.parse_ack(response)

                    if protocol == "GBN":
                        acked_until = ack_seq
                        for i in range(base, acked_until):
                            pass
                        base = acked_until
                        print_window(base, next_seq_num)
                    elif protocol == "SR":
                        for idx in range(base, min(base + WINDOW_SIZE, total_packets)):
                            if idx % 256 == ack_seq:
                                acked[idx] = True
                                break
                        while base < total_packets and acked[base]:
                            base += 1
                            print_window(base, next_seq_num)

                except socket.timeout:
                    current_time = time.time()
                    for idx in range(base, min(base + WINDOW_SIZE, total_packets)):
                        if not acked[idx] and (current_time - timers.get(idx, current_time)) > TIMEOUT:
                            packet = common_utils.create_packet(idx % 256, packets[idx])
                            client_socket.sendall(packet)
                            timers[idx] = time.time()

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        client_socket.close()
        print("Conexão encerrada.")

if __name__ == "__main__":
    start_client()