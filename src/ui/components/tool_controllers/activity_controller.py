# app/ui_components/tool_controllers/activity_controller.py

import logging
from .base_controller import BaseToolController, Q_ITEM_CALLBACK
from datetime import datetime, time, timedelta
from ..activity_help_dialog import ActivityHelpDialog
from ..activity_frame import ActivityFrame

class ActivityController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)
        self.period_key_map = {
            "period_today": "Hoje",
            "period_yesterday": "Ontem",
            "period_this_week": "Esta Semana",
            "period_last_week": "Semana Passada",
            "period_this_month": "Este Mês",
            "period_last_month": "Mês Passado"
        }

    def handle_activity_tab_first_load(self, parent_frame):
        if parent_frame.winfo_children():
            return
            
        if self.app.show_activity_help_dialog:
            # CORREÇÃO: Chamada simplificada para o novo construtor
            dialog = ActivityHelpDialog(self.app)
            # CORREÇÃO: Adicionado wait() para pausar a execução até o diálogo ser fechado
            dialog.wait() 
            dont_show_again = dialog.get_result()
            
            if dont_show_again:
                self.app.show_activity_help_dialog = False
        
        activity_frame = ActivityFrame(parent_frame, self.app, self.host, self)
        activity_frame.pack(fill="both", expand=True)

    def _get_date_range(self, period_key):
        today = datetime.now().date()
        
        if period_key == "Hoje":
            start_dt = datetime.combine(today, time.min)
            end_dt = datetime.now()
        elif period_key == "Ontem":
            yesterday = today - timedelta(days=1)
            start_dt = datetime.combine(yesterday, time.min)
            end_dt = datetime.combine(yesterday, time.max)
        elif period_key == "Esta Semana":
            start_of_week = today - timedelta(days=today.weekday())
            start_dt = datetime.combine(start_of_week, time.min)
            end_dt = datetime.now()
        elif period_key == "Semana Passada":
            end_of_last_week = today - timedelta(days=today.weekday() + 1)
            start_of_last_week = end_of_last_week - timedelta(days=6)
            start_dt = datetime.combine(start_of_last_week, time.min)
            end_dt = datetime.combine(end_of_last_week, time.max)
        elif period_key == "Este Mês":
            start_of_month = today.replace(day=1)
            start_dt = datetime.combine(start_of_month, time.min)
            end_dt = datetime.now()
        elif period_key == "Mês Passado":
            end_of_last_month = today.replace(day=1) - timedelta(days=1)
            start_of_last_month = end_of_last_month.replace(day=1)
            start_dt = datetime.combine(start_of_last_month, time.min)
            end_dt = datetime.combine(end_of_last_month, time.max)
        else:
            return None, None
            
        return start_dt, end_dt

    def fetch_activity_data(self, period_str_translated, callback_update_ui):
        logic_key = "Hoje" 
        for key, name in self.period_key_map.items():
            if self.app.translate(key) == period_str_translated:
                logic_key = name
                break

        start_dt, end_dt = self._get_date_range(logic_key)
        if not start_dt:
            return

        loading_text = self.app.translate("activity_loading_text", period=period_str_translated)
        self._start_command("get_activity", self._fetch_activity_worker,
                            args_tuple=(start_dt, end_dt, callback_update_ui),
                            needs_auth=True,
                            loading_text=loading_text)

    def _fetch_activity_worker(self, username, password, start_dt, end_dt, callback_update_ui):
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        
        event_generator = self.system_tools.get_remote_activity_events(self.host['ip'], username, password, start_iso, end_iso)
        events = next(event_generator, [])
        
        logging.info(f"Activity analysis: Found {len(events)} events for period {start_dt} to {end_dt}")
        for i, event in enumerate(events):
            logging.info(f"Event {i}: Type={event.get('Type', 'Unknown')}, Time={event.get('Time', 'Unknown')}, User={event.get('User', 'Unknown')}")

        if isinstance(events, dict) and "error" in events:
            if self._is_winrm_connection_error(events.get("exception_obj")):
                 self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_ui, ({'error': events['error']},), {}))
            return
        
        if not events:
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_ui, ({'active': timedelta(0), 'idle': timedelta(0)},), {}))
            return

        active_duration = timedelta()
        idle_duration = timedelta()
        last_event_time = start_dt
        is_active = False 

        # Mapeamento de tipos de eventos para determinar atividade
        active_events = ['Logon', 'Unlock', 'Reconnect', 'CurrentSession', 'ProcessActivity', 'ActiveSession', 'Boot']
        inactive_events = ['Logoff', 'Lock', 'Disconnect', 'Shutdown', 'UnexpectedShutdown', 'IdleSession', 'NoUsers']

        # Determinar estado inicial baseado em eventos antes do período
        initial_state_events = sorted([e for e in events if datetime.fromisoformat(e['Time'].replace("Z", "+00:00")).replace(tzinfo=None) < start_dt], key=lambda x: x['Time'], reverse=True)
        if initial_state_events:
            last_event_before_period = initial_state_events[0]
            if last_event_before_period['Type'] in active_events:
                is_active = True
        else:
            # Se não há eventos anteriores, ser mais conservador
            # Só considerar ativo se houver evidências claras de atividade
            current_session_events = [e for e in events if e['Type'] in ['CurrentSession', 'ProcessActivity', 'ActiveSession']]
            if current_session_events:
                # Verificar se é realmente uma sessão ativa
                for event in current_session_events:
                    if event['Type'] == 'CurrentSession' and event.get('User') == 'Active':
                        is_active = True
                        break
                    elif event['Type'] == 'ActiveSession':
                        is_active = True
                        break
                    elif event['Type'] == 'ProcessActivity':
                        is_active = True
                        break

        logging.info(f"Initial state determined: is_active={is_active}")

        # Processar eventos dentro do período
        for event in sorted(events, key=lambda x: x['Time']):
            event_time = datetime.fromisoformat(event['Time'].replace("Z", "+00:00")).replace(tzinfo=None)
            
            if event_time < start_dt or event_time > end_dt:
                continue
            
            duration_since_last = event_time - last_event_time
            
            if is_active:
                active_duration += duration_since_last
            else:
                idle_duration += duration_since_last

            # Atualizar estado baseado no tipo de evento
            if event['Type'] in active_events:
                # Ser mais conservador com CurrentSession
                if event['Type'] == 'CurrentSession':
                    if event.get('User') == 'Active':
                        is_active = True
                        logging.info(f"Event {event['Type']} with User=Active -> Setting active=True")
                    else:
                        is_active = False
                        logging.info(f"Event {event['Type']} with User={event.get('User', 'Unknown')} -> Setting active=False")
                else:
                    is_active = True
                    logging.info(f"Event {event['Type']} -> Setting active=True")
            elif event['Type'] in inactive_events:
                is_active = False
                logging.info(f"Event {event['Type']} -> Setting active=False")
            
            last_event_time = event_time

        # Processar tempo final até o fim do período
        final_duration = end_dt - last_event_time
        if final_duration > timedelta(0):
            if is_active:
                active_duration += final_duration
            else:
                idle_duration += final_duration

        # Se não há eventos de atividade, verificar se há sessão atual
        if active_duration == timedelta(0) and idle_duration == timedelta(0):
            session_events = [e for e in events if e['Type'] in ['CurrentSession', 'ProcessActivity', 'ActiveSession']]
            if session_events:
                # Verificar se a sessão atual é realmente ativa
                current_session = session_events[0]
                if current_session['Type'] == 'CurrentSession':
                    # Se há usuário logado, considerar como potencialmente ativo
                    # mas não assumir 100% ativo sem evidências
                    active_duration = timedelta(minutes=30)  # Assumir 30 min ativo
                    idle_duration = end_dt - start_dt - active_duration
                else:
                    # Para outros tipos de eventos, ser mais conservador
                    active_duration = timedelta(minutes=15)
                    idle_duration = end_dt - start_dt - active_duration
            else:
                # Se não há eventos de sessão, considerar como ocioso
                idle_duration = end_dt - start_dt
                active_duration = timedelta(0)
        
        results = {'active': active_duration, 'idle': idle_duration}
        logging.info(f"Activity analysis result: Active={active_duration}, Idle={idle_duration}, Total={active_duration + idle_duration}")
        
        self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_ui, (results,), {}))
        
        # Finalizar o comando para fechar a janela de loading (agora tratado pelo thread_wrapper)