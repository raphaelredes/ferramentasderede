# app/ui_components/tool_controllers/network_tool_controller.py

import threading
import socket
import logging
from .base_controller import BaseToolController, Q_ITEM_TEXT, Q_ITEM_CALLBACK

class NetworkToolController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)

    def start_standalone_ping(self, target, packet_size_str, output_widget):
        """Inicia um ping para um alvo arbitrário, usado pela aba Home."""
        self.output_textbox = output_widget
        if not target:
            self.app.show_error(self.app.translate("error_target_empty"), widget_to_focus=output_widget.master.winfo_children()[0].winfo_children()[0])
            return
        try:
            packet_size = int(packet_size_str) if packet_size_str else 32
            if packet_size > 65500: packet_size = 65500
        except ValueError:
            self.app.show_error(self.app.translate("error_invalid_packet_size"), widget_to_focus=output_widget.master.winfo_children()[0].winfo_children()[1].winfo_children()[1])
            return
        
        # Usar worker específico que aceita target como parâmetro para evitar conflito de referência
        self._start_command(f"ping_{target}", self._standalone_ping_worker, args_tuple=(target, packet_size))

    def _standalone_ping_worker(self, target, packet_size):
        """Worker simplificado e robusto para ping standalone"""
        process = None
        
        logging.info(f"PING: Iniciando ping para {target}, packet_size: {packet_size}")
        
        try:
            # Executar ping com verificação frequente de is_running
            for line, process in self.network_tools.continuous_ping(target, packet_size):
                # Armazenar processo para poder cancelar
                self.current_process = process
                
                # VERIFICAÇÃO CRÍTICA - sair imediatamente se cancelado
                if not self.is_running:
                    logging.info(f"PING: Cancelado pelo usuário - target: {target}")
                    break
                    
                # Enviar output diretamente para o textbox
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", line)
                        self.output_textbox.see("end")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass  # Se não conseguir escrever, continuar ping
                    
        except Exception as e:
            logging.error(f"PING: Erro para {target}: {e}")
            
            # Mostrar erro diretamente
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\nErro no ping: {e}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            # LIMPEZA SIMPLIFICADA
            logging.info(f"PING: Finalizando worker para {target}")
            
            # Terminar processo se ainda estiver rodando
            if process:
                try:
                    process.terminate()
                    import time
                    time.sleep(0.1)
                    if process.poll() is None:
                        process.kill()
                except:
                    pass
                    
            logging.info(f"PING: Worker finalizado para {target}")

    def start_standalone_traceroute(self, target, output_widget):
        """Inicia um traceroute para um alvo arbitrário, usado pela aba Home."""
        self.output_textbox = output_widget
        if not target:
            self.app.show_error(self.app.translate("error_target_empty"), widget_to_focus=output_widget.master.winfo_children()[0].winfo_children()[0])
            return

        # Usar worker específico que aceita target como parâmetro
        self._start_command(f"traceroute_{target}", self._standalone_traceroute_worker, args_tuple=(target,))

    def _standalone_traceroute_worker(self, target):
        """Worker simplificado e robusto para traceroute standalone"""
        logging.info(f"TRACEROUTE: Iniciando traceroute para {target}")
        
        try:
            # Executar traceroute com verificação frequente de is_running
            for line in self.network_tools.traceroute(target):
                # VERIFICAÇÃO CRÍTICA - sair imediatamente se cancelado
                if not self.is_running:
                    logging.info(f"TRACEROUTE: Cancelado pelo usuário - target: {target}")
                    break
                    
                # Enviar output diretamente para o textbox
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", line)
                        self.output_textbox.see("end")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass  # Se não conseguir escrever, continuar traceroute
                    
        except Exception as e:
            logging.error(f"TRACEROUTE: Erro para {target}: {e}")
            
            # Mostrar erro diretamente
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\nErro no traceroute: {e}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            logging.info(f"TRACEROUTE: Worker finalizado para {target}")

    def _ping_worker(self, packet_size):
        """Worker simplificado e robusto para ping normal (abas de hosts)"""
        process = None
        
        logging.info(f"PING: Iniciando ping para {self.host['ip']}, packet_size: {packet_size}")
        
        try:
            # Executar ping com verificação frequente de is_running
            for line, process in self.network_tools.continuous_ping(self.host['ip'], packet_size):
                # Armazenar processo para poder cancelar
                self.current_process = process
                
                # VERIFICAÇÃO CRÍTICA - sair imediatamente se cancelado
                if not self.is_running:
                    logging.info(f"PING: Cancelado pelo usuário - IP: {self.host['ip']}")
                    break
                    
                # Enviar output diretamente para o textbox
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", line)
                        self.output_textbox.see("end")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass  # Se não conseguir escrever, continuar ping
                    
        except Exception as e:
            logging.error(f"PING: Erro para {self.host['ip']}: {e}")
            
            # Mostrar erro diretamente
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\nErro no ping: {e}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            # LIMPEZA SIMPLIFICADA
            logging.info(f"PING: Finalizando worker para {self.host['ip']}")
            
            # Terminar processo se ainda estiver rodando
            if process:
                try:
                    process.terminate()
                    import time
                    time.sleep(0.1)
                    if process.poll() is None:
                        process.kill()
                except:
                    pass
                    
            logging.info(f"PING: Worker finalizado para {self.host['ip']}")

    def start_ping(self, packet_size_str, output_widget, entry_widget_to_focus=None):
        self.output_textbox = output_widget
        try:
            # Garantir que sempre tenha um valor válido
            if not packet_size_str or packet_size_str.strip() == "":
                packet_size = 32
            else:
                packet_size = int(packet_size_str.strip())
            
            if packet_size > 65500: 
                packet_size = 65500
            elif packet_size < 1:
                packet_size = 32
                
        except ValueError:
            self.app.show_error(self.app.translate("error_invalid_packet_size"), widget_to_focus=entry_widget_to_focus)
            return
        
        # Passar IP do host para o backend compatível, caso seja usado
        self._start_command("ping", self._ping_worker, args_tuple=(packet_size,))

    def _test_ports_worker(self, ports_str):
        logging.info(f"_test_ports_worker iniciado para IP: {self.host['ip']}, ports: {ports_str}")
        try:
            logging.info(f"Chamando network_tools.test_specific_ports para {self.host['ip']}")
            for line in self.network_tools.test_specific_ports(self.host['ip'], ports_str):
                if not self.is_running: break
                self._put_in_queue(Q_ITEM_TEXT, line)
        except Exception as e:
            logging.error(f"Erro no teste de portas: {e}")
            self._put_in_queue(Q_ITEM_TEXT, f"Erro no teste de portas: {e}\n")
        finally:
            # Garantir finalização do comando (agora tratado pelo thread_wrapper)
            pass
            
    def test_ports(self, ports_str, output_widget, entry_widget_to_focus=None):
        self.output_textbox = output_widget
        if not ports_str:
            ports_str = "80"
        self._start_command("test_ports", self._test_ports_worker, args_tuple=(ports_str,))

    def _port_scan_worker(self):
        try:
            for line in self.network_tools.scan_top_ports(self.host['ip']):
                if not self.is_running: break
                self._put_in_queue(Q_ITEM_TEXT, line)
        except Exception as e:
            logging.error(f"Erro no escaneamento de portas: {e}")
            self._put_in_queue(Q_ITEM_TEXT, f"Erro no escaneamento de portas: {e}\n")
        finally:
            # Garantir finalização do comando (agora tratado pelo thread_wrapper)
            pass
            
    def _all_ports_scan_worker(self):
        try:
            for line in self.network_tools.scan_all_ports(self.host['ip']):
                if not self.is_running: break
                self._put_in_queue(Q_ITEM_TEXT, line)
        except Exception as e:
            logging.error(f"Erro no escaneamento de todas as portas: {e}")
            self._put_in_queue(Q_ITEM_TEXT, f"Erro no escaneamento de todas as portas: {e}\n")
        finally:
            # Garantir finalização do comando (agora tratado pelo thread_wrapper)
            pass

    def start_port_scan(self, output_widget):
        self.output_textbox = output_widget
        self._start_command("scan", self._port_scan_worker)
        
    def start_all_ports_scan(self, output_widget):
        self.output_textbox = output_widget
        self._start_command("scan", self._all_ports_scan_worker)

    def _traceroute_worker(self):
        """Worker simplificado e robusto para traceroute normal (abas de hosts)"""
        logging.info(f"TRACEROUTE: Iniciando traceroute para {self.host['ip']}")
        
        try:
            # Executar traceroute com verificação frequente de is_running
            for line in self.network_tools.traceroute(self.host['ip']):
                # VERIFICAÇÃO CRÍTICA - sair imediatamente se cancelado
                if not self.is_running:
                    logging.info(f"TRACEROUTE: Cancelado pelo usuário - IP: {self.host['ip']}")
                    break
                    
                # Enviar output diretamente para o textbox
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", line)
                        self.output_textbox.see("end")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass  # Se não conseguir escrever, continuar traceroute
                    
        except Exception as e:
            logging.error(f"TRACEROUTE: Erro para {self.host['ip']}: {e}")
            
            # Mostrar erro diretamente
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\nErro no traceroute: {e}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            logging.info(f"TRACEROUTE: Worker finalizado para {self.host['ip']}")

    def run_traceroute(self, output_widget):
        self.output_textbox = output_widget
        self._start_command("traceroute", self._traceroute_worker)