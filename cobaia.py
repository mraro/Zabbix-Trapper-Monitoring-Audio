import configparser
import socket
########################
import sys
import threading
import time

import numpy as np
import pyaudio
from PyQt5 import QtCore
from PyQt5.QtGui import QIcon, QIntValidator
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, \
    QComboBox, QSystemTrayIcon
from PyQt5.QtCore import Qt

from equalizer_bar import EqualizerBar


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.p = None
        self.CHUNK = 2 ** 11
        self.RATE = 44100

        self.equalizer = None
        self.microphone_combobox = None
        self.port_input = None
        self.server_input = None
        self.hostname_input = None
        self.setWindowTitle("Configurações de Áudio")
        self.setGeometry(100, 100, 400, 300)
        self.initUI()
        self.populate_microphones()

        node = threading.Thread(target=self.current)
        node.start()

    def initUI(self):
        try:
            # Widgets para as configurações de servidor
            server_label = QLabel("Server:")
            self.server_input = QLineEdit()
            self.server_input.setInputMask("000.000.000.000;_")
            self.server_input.setPlaceholderText("Endereço IPv4")

            port_label = QLabel("Port:")
            self.port_input = QLineEdit()
            self.port_input.setValidator(QIntValidator())
            self.port_input.setMaxLength(5)

            hostname_label = QLabel("Hostname:")
            self.hostname_input = QLineEdit()

            # Carregar valores padrão dos parâmetros salvos, se existirem
            config = configparser.ConfigParser()
            config.read('config.ini')
            if 'Servidor' in config:
                server_config = config['Servidor']
                self.server_input.setText(server_config.get('Endereço', ''))
                self.port_input.setText(server_config.get('Porta', '10051'))
                self.hostname_input.setText(server_config.get('Hostname', socket.gethostname()))

            # Botão de salvar
            save_button = QPushButton("Salvar")
            save_button.clicked.connect(self.save_settings)

            # Layout para as configurações de servidor
            server_layout = QVBoxLayout()
            server_layout.addWidget(server_label)
            server_layout.addWidget(self.server_input)
            server_layout.addWidget(port_label)
            server_layout.addWidget(self.port_input)
            server_layout.addWidget(hostname_label)
            server_layout.addWidget(self.hostname_input)
            server_layout.addWidget(save_button)

            # ComboBox para os microfones disponíveis
            microphone_label = QLabel("Microfone:")
            self.microphone_combobox = QComboBox()
            # Adicione aqui a lógica para preencher a combobox com os microfones disponíveis no Windows

            # Layout para a combobox do microfone
            microphone_layout = QVBoxLayout()
            microphone_layout.addWidget(microphone_label)
            microphone_layout.addWidget(self.microphone_combobox)

            # Equalizer
            self.equalizer = EqualizerBar(2,
                                          ['#0C0786', '#40039C', '#6A00A7', '#8F0DA3', '#B02A8F', '#CA4678', '#E06461',
                                           '#F1824C', '#FCA635', '#FCCC25', '#EFF821'])
            microphone_layout.addWidget(self.equalizer)

            # Widgets para as configurações de servidor
            self.log_label = QLabel("Log:")
            self.log_text = QLabel("")
            self.log_text.setWordWrap(True)

            # Layout para a label de log
            log_layout = QVBoxLayout()
            log_layout.addWidget(self.log_label)
            log_layout.addWidget(self.log_text)

            # Layout principal
            main_layout = QVBoxLayout()

            # Layout para as configurações de servidor e microfone
            server_microphone_layout = QHBoxLayout()
            server_microphone_layout.addLayout(server_layout)
            server_microphone_layout.addSpacing(20)  # Adicionando um espaçador
            server_microphone_layout.addLayout(microphone_layout)

            # Adicionando layouts ao layout principal
            main_layout.addLayout(server_microphone_layout)
            main_layout.addStretch(1)  # Adicionando um espaçador elástico
            main_layout.addLayout(log_layout)  # Adicionando a layout de log ao layout principal

            self.setLayout(main_layout)
        except Exception as e:
            print('error on UI:', e)

    def update_log(self, message):
        # Atualizar o texto da label de log
        self.log_text.setText(message)

    def save_settings(self):
        try:
            # Salvar os parâmetros do usuário em um arquivo de configuração
            config = configparser.ConfigParser()
            config['Servidor'] = {
                'Endereço': self.server_input.text(),
                'Porta': self.port_input.text(),
                'Hostname': self.hostname_input.text()
            }

            with open('config.ini', 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            print('error on send data:', e)

    def send_data_zabbix(self):
        try:
            # Ler os parâmetros do arquivo de configuração
            config = configparser.ConfigParser()
            config.read('config.ini')

            if 'Servidor' in config:
                server_config = config['Servidor']
                endereco = server_config.get('Endereço', '')
                porta = server_config.get('Porta', '')
                hostname = server_config.get('Hostname', '')
                return endereco, porta, hostname
            else:
                return '', '', ''

        except Exception as e:
            print('error on send data:', e)

    # def update_values(self, value):
    #     return value
    # ...
    #     self.equalizer.setValues([
    #         min(100, v+random.randint(0, 20) if random.randint(0, 2) > 2 else v)
    #         for v in self.equalizer.values()
    #         ])
    #     print(self.equalizer.values())

    def populate_microphones(self):
        p = pyaudio.PyAudio()
        info = p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        list_microphones = []
        for i in range(numdevices):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                device_name = device_info['name']
                if device_name not in list_microphones:
                    list_microphones.append(device_name)
                    self.microphone_combobox.addItem(device_name)

                    # print(i)

    def streaming_audio_data(self, stream):
        if self.p:
            try:
                data = np.frombuffer(stream.read(self.CHUNK), dtype=np.int16)
                peak = np.average(np.abs(data)) * 2
                zabbix_data = int(50 * peak / 2 ** 16)
                self.equalizer.setValues([zabbix_data, peak])
                print(peak)
                # enviar_valores_para_zabbix(zabbix_data)
            except Exception as e:
                self.p.close()
                self.update_log(f"FALHA reinicie o app pelo gerenciador de tarefas\n {e}")

    def current(self):
        current = self.microphone_combobox.currentIndex()

        p = pyaudio.PyAudio()
        # init
        stream = p.open(input_device_index=0,
                        format=pyaudio.paInt16,
                        channels=2,
                        rate=self.RATE,
                        input=True,
                        frames_per_buffer=self.CHUNK)

        while True:
            last = self.microphone_combobox.currentIndex()
            if current != last:
                current = last
                print(current)
                p.close(stream)
                p = pyaudio.PyAudio()
                # print('change')
                try:
                    stream = p.open(input_device_index=current,
                                    format=pyaudio.paInt16,
                                    channels=2,
                                    rate=self.RATE,
                                    input=True,
                                    frames_per_buffer=self.CHUNK)
                    print('estereo')

                except OSError:
                    stream = p.open(input_device_index=current,
                                    format=pyaudio.paInt16,
                                    channels=1,
                                    rate=self.RATE,
                                    input=True,
                                    frames_per_buffer=self.CHUNK)
                    print('mono')

            else:
                try:
                    time.sleep(1)

                    if stream.get_read_available() > 1:
                        self.update_log("")

                        # print(stream)
                        stream_data = stream.read(self.CHUNK)
                        data = np.frombuffer(stream_data, dtype=np.int16)
                        # peak = np.average(np.abs(data)) * 2
                        # zabbix_data = int(50 * peak / 2 ** 16)
                        # self.equalizer.setValues([zabbix_data, 0])

                        peak_max = max(np.max(np.abs(data)), np.max(np.abs(data)))

                        # Normalize os valores de amplitude com base no pico máximo
                        if peak_max > 0:
                            peak = (np.abs(data) / peak_max) * 100
                        else:
                            peak = np.zeros_like(data)
                        print(peak)
                        # enviar_valores_para_zabbix(zabbix_data)
                    else:
                        self.update_log("Troca o microfone, impossivel de ler" + str(current))
                except Exception as e:
                    self.update_log(f"FALHA reinicie o app pelo gerenciador de tarefas\n {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    QSystemTrayIcon(QIcon("icone.ico"), app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())