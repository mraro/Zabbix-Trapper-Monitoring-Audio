import configparser
import socket
import sys
import time

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QIcon, QIntValidator
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, \
    QHBoxLayout, QWidget, QComboBox, QMenu
import pyqtgraph as pg
from pyzabbix import ZabbixMetric, ZabbixSender

from equalizer_bar import EqualizerBar
import pyaudio
import numpy as np
import threading


class Autoparse:
    def __init__(self):
        self.p = None
        self.CHUNK = 2 ** 11
        self.RATE = 44100
        self.data = np.zeros(10)

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.trayIcon = QSystemTrayIcon(self.app)
        self.menu = self.create_menu()
        self.trayIcon.setContextMenu(self.menu)
        self.trayIcon.setIcon(QIcon("icone.ico"))
        self.trayIcon.show()

        self.config_window = None
        self.open_config_window()

        self.populate_microphones()

        node = threading.Thread(target=self.current)
        node.start()

        try:
            self.zabbix_server, self.zabbix_port, self.zabbix_host = self.read_config_ini()
        except Exception as e:
            self.update_log(f"FALHA ao ler arquivo config.ini - \n {e}")

        sys.exit(self.app.exec_())

    def create_menu(self):
        menu = QMenu()
        autopconfig_action = menu.addAction('Config')
        autopconfig_action.triggered.connect(self.open_config_window)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.app.quit)
        return menu

    def open_config_window(self):
        if not self.config_window:
            self.config_window = QMainWindow()
            self.config_window.setWindowTitle("Configurações de Áudio")
            # self.config_window.setGeometry(100, 100, 500, 300)
            # Widgets para as configurações de servidor
            server_label = QLabel("Server:")
            self.server_input = QLineEdit()
            self.server_input.setInputMask("000.000.000.000; ")
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
            else:
                self.port_input.setText('10051')
                self.hostname_input.setText(socket.gethostname())

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
            # self.equalizer = EqualizerBar(1,
            #                               ['#0C0786', '#40039C', '#6A00A7', '#8F0DA3', '#B02A8F', '#CA4678', '#E06461',
            #                                '#F1824C', '#FCA635', '#FCCC25', '#EFF821'])

            # Plot Widget
            self.equalizer = pg.PlotWidget()
            # Configurar o gráfico inicial
            self.plot_curve = self.equalizer.plot(self.data, pen='b')
            self.timer = pg.QtCore.QTimer()
            self.timer.timeout.connect(self.update_plot)
            self.timer.start(500)  # Atualiza a cada 1 segundo

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

            central_widget = QWidget()
            central_widget.setLayout(main_layout)

            self.config_window.setCentralWidget(central_widget)

        self.config_window.show()

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

    def read_config_ini(self):
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
            self.update_log('error on config file:', e)

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

    def send_data_to_zabbix_trapper(self, valor):
        metrics = ZabbixMetric(str(self.zabbix_host), "app.lista_valores", valor)
        sender = ZabbixSender(self.zabbix_server, int(self.zabbix_port))
        sender.send([metrics])

    def update_plot(self):
        print(self.data)

        return self.plot_curve.setData(self.data)

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
                    time.sleep(0.01)

                    if stream.get_read_available() > 1:
                        self.update_log("")

                        # print(stream)
                        stream_data = stream.read(self.CHUNK)
                        data = np.frombuffer(stream_data, dtype=np.int16)
                        # peak = np.average(np.abs(data)) * 2
                        # zabbix_data = int(50 * peak / 2 ** 16)
                        # data = (data - 0) / (np.max(data) - 0)
                        data = (np.average(np.abs(data))) * 0.01
                        # print(data)
                        self.data[:-1] = self.data[1:]  # Shift dos valores para a esquerda
                        self.data[-1] = data

                        self.send_data_to_zabbix_trapper(int(data))

                        # data = data * 100
                        # if data > 99:
                        #     data = 99

                        # print(data)
                        # self.update_plot(data)

                        # Atualiza o gráfico
                        # self.equalizer.setValues([data])
                        # enviar_valores_para_zabbix(zabbix_data)
                    else:
                        self.update_log("Troca o microfone, impossivel de ler" + str(current))
                except Exception as e:
                    self.update_log(f"FALHA reinicie o app pelo gerenciador de tarefas\n {e}")


if __name__ == "__main__":
    Autoparse()
