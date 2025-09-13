# src/ferramentasderede/ui/components/tab_status_indicator.py
# Gerencia indicadores de status nas abas de host.

import customtkinter
import threading
import time

class TabStatusIndicator:
    """Gerencia indicadores de status nas abas de host."""
    
    def __init__(self, tab_view):
        self.tab_view = tab_view
        self.status_indicators = {}  # {tab_name: indicator_widget}
        self.running_commands = {}   # {tab_name: command_name}
        
    def create_status_indicator(self, tab_name):
        """Cria um indicador de status para uma aba."""
        # DESABILITADO: Não criar indicadores flutuantes
        # Os indicadores de status agora são mostrados dentro das sub-abas
        # via CommandStatusWidget
        
        # Retorna um objeto dummy para manter compatibilidade
        if tab_name not in self.status_indicators:
            self.status_indicators[tab_name] = {
                'frame': None,
                'indicator': None,
                'thread': None,
                'blink_state': False
            }
        
        return self.status_indicators[tab_name]
        
    def start_command(self, tab_name, command_name):
        """Inicia um comando e mostra o indicador laranja piscando."""
        import logging
        logging.debug(f"STATUS: Indicadores flutuantes desabilitados - comando '{command_name}' na aba '{tab_name}' será mostrado via CommandStatusWidget")
        
        # DESABILITADO: Não mostrar indicadores flutuantes
        # Os indicadores de status agora são mostrados dentro das sub-abas
        # via CommandStatusWidget
        
        # Apenas registrar comando em execução para compatibilidade
        self.running_commands[tab_name] = command_name
        
    def finish_command(self, tab_name, success=True):
        """Finaliza um comando e mostra o indicador verde temporariamente."""
        import logging
        logging.debug(f"STATUS: Indicadores flutuantes desabilitados - finalização de comando '{tab_name}' sucesso={success} será mostrada via CommandStatusWidget")
        
        # DESABILITADO: Não mostrar indicadores flutuantes
        # Os indicadores de status agora são mostrados dentro das sub-abas
        # via CommandStatusWidget
        
        # Apenas remover comando da lista para compatibilidade
        if tab_name in self.running_commands:
            del self.running_commands[tab_name]
        
    def _position_indicator(self, tab_name):
        """Posiciona o indicador na aba correta de forma mais robusta."""
        try:
            # DESABILITADO: Não mostrar indicadores que ficam próximo aos botões
            # Os indicadores de status agora são mostrados dentro das sub-abas
            # via CommandStatusWidget em vez de flutuantes no tab_view
            pass
                
        except Exception as e:
            import logging
            logging.debug(f"Erro ao posicionar indicador para '{tab_name}': {e}")
            
    def hide_indicator(self, tab_name):
        """Esconde o indicador de uma aba com limpeza adequada."""
        import logging
        logging.debug(f"STATUS: Indicadores flutuantes desabilitados - hide_indicator para '{tab_name}' ignorado")
        
        # DESABILITADO: Não há mais indicadores flutuantes para esconder
        # Os indicadores de status agora são mostrados dentro das sub-abas
        # via CommandStatusWidget
            
    def clear_all_indicators(self):
        """Limpa todos os indicadores."""
        import logging
        logging.debug("STATUS: Indicadores flutuantes desabilitados - clear_all_indicators apenas limpa estruturas de dados")
        
        # DESABILITADO: Não há mais indicadores flutuantes para limpar
        # Apenas limpar estruturas de dados para compatibilidade
        self.status_indicators.clear()
        self.running_commands.clear()
        
    class _BlinkThread(threading.Thread):
        """Thread thread-safe para fazer o indicador piscar."""
        
        def __init__(self, indicator_data, tab_view):
            super().__init__(daemon=True)
            self.indicator_data = indicator_data
            self.tab_view = tab_view
            self.stop_flag = False
            
        def run(self):
            while not self.stop_flag:
                try:
                    # Agendar atualização da UI de forma thread-safe
                    if hasattr(self.tab_view, 'after_idle') and not self.stop_flag:
                        self.tab_view.after_idle(self._update_blink_state)
                    time.sleep(0.5)
                except Exception as e:
                    import logging
                    logging.debug(f"Erro em _BlinkThread: {e}")
                    break
        
        def _update_blink_state(self):
            """Atualiza o estado do piscar de forma thread-safe."""
            try:
                if self.stop_flag:
                    return
                    
                # Alternar estado do piscar
                self.indicator_data['blink_state'] = not self.indicator_data['blink_state']
                
                if self.indicator_data['indicator'].winfo_exists():
                    if self.indicator_data['blink_state']:
                        self.indicator_data['indicator'].configure(fg_color="orange")
                    else:
                        self.indicator_data['indicator'].configure(fg_color="darkorange")
            except Exception as e:
                import logging
                logging.debug(f"Erro em _update_blink_state: {e}")
                self.stop_flag = True
                    
        def stop(self):
            self.stop_flag = True
            
    class _HideThread(threading.Thread):
        """Thread thread-safe para esconder o indicador após alguns segundos."""
        
        def __init__(self, indicator_data, tab_view):
            super().__init__(daemon=True)
            self.indicator_data = indicator_data
            self.tab_view = tab_view
            
        def run(self):
            time.sleep(3)  # Esperar 3 segundos
            try:
                # Agendar esconder de forma thread-safe
                if hasattr(self.tab_view, 'after_idle'):
                    self.tab_view.after_idle(self._hide_indicator)
            except Exception as e:
                import logging
                logging.debug(f"Erro em _HideThread: {e}")
                
        def _hide_indicator(self):
            """Esconde o indicador de forma thread-safe."""
            try:
                if self.indicator_data['frame'].winfo_exists():
                    self.indicator_data['frame'].place_forget()
            except Exception as e:
                import logging
                logging.debug(f"Erro ao esconder indicador: {e}")
