"""
MAVLink Parameter Uploader Module (High-Success Mode - Fast Burst Upload)
Supports parameter fetching, value comparison, fast pipelined burst upload, and buffer draining.
"""

import time
import sys
from typing import Dict, List, Tuple, Callable, Optional
from pymavlink import mavutil

class MavParamUploader:
    def __init__(self, connection_string: str = 'COM7', baud: int = 115200, timeout: float = 5.0):
        """
        Initializes MAVLink connection.
        """
        self.connection_string = connection_string
        self.baud = baud
        self.timeout = timeout
        self.master = None
        self.vehicle_params = {}

    def connect(self):
        """Establishes MAVLink connection and waits for vehicle heartbeat with auto-fallback for Ubuntu SITL."""
        raw_conn = ''.join(self.connection_string.split())
        
        candidates = [raw_conn]
        if raw_conn.startswith('udp:') and not raw_conn.startswith('udpout:') and not raw_conn.startswith('udpin:'):
            candidates[0] = raw_conn.replace('udp:', 'udpin:')
            
        # Add SITL fallbacks if network connection is targeted
        if any(raw_conn.startswith(p) for p in ['udp', 'tcp', '127.', '0.0.0.0', 'localhost']):
            for fallback in ['udpin:0.0.0.0:14551', 'tcp:127.0.0.1:5760', 'tcp:127.0.0.1:5762', 'udpin:0.0.0.0:14550']:
                if fallback not in candidates:
                    candidates.append(fallback)

        connected = False
        last_error = None

        for conn in candidates:
            print(f"[MAVLink] Connecting to vehicle on '{conn}' (baud: {self.baud})...")
            try:
                self.master = mavutil.mavlink_connection(conn, baud=self.baud)
                print(f"[MAVLink] Waiting for vehicle heartbeat on '{conn}'...")
                timeout_sec = 3.0 if (len(candidates) > 1 and conn != candidates[-1]) else self.timeout
                heartbeat = self.master.wait_heartbeat(timeout=timeout_sec)
                if heartbeat:
                    self.connection_string = conn
                    connected = True
                    print(f"[MAVLink] Heartbeat received from System {self.master.target_system}, Component {self.master.target_component} on '{conn}'")
                    break
                else:
                    self.master.close()
                    self.master = None
            except Exception as e:
                last_error = e
                if self.master:
                    try:
                        self.master.close()
                    except Exception:
                        pass
                    self.master = None

        if not connected:
            raise TimeoutError(
                f"No MAVLink heartbeat received on {self.connection_string} within {self.timeout}s.\n"
                f"For Ubuntu SITL, ensure sim_vehicle.py or MAVProxy is running with --out=udp:127.0.0.1:14551 or TCP 5760/5762."
            )
        return True

    def fetch_all_vehicle_params(self, timeout: float = 6.0) -> Dict[str, float]:
        """
        Requests full parameter list from the vehicle at high speed.
        Completes immediately when total count is reached or idle timeout hits.
        """
        if not self.master:
            self.connect()

        print("[MAVLink] Requesting parameter list from vehicle...")
        self.master.mav.param_request_list_send(
            self.master.target_system,
            self.master.target_component
        )

        start_time = time.time()
        fetched = {}
        last_recv_time = time.time()
        expected_count = None

        while time.time() - start_time < timeout:
            msg = self.master.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.1)
            if msg is not None:
                last_recv_time = time.time()
                if hasattr(msg, 'param_count') and msg.param_count > 0:
                    expected_count = msg.param_count

                raw_id = msg.param_id
                if isinstance(raw_id, str):
                    p_name = raw_id.rstrip('\x00').strip().upper()
                elif isinstance(raw_id, bytes):
                    p_name = raw_id.rstrip(b'\x00').decode('ascii', errors='ignore').strip().upper()
                else:
                    p_name = str(raw_id).rstrip('\x00').strip().upper()
                
                fetched[p_name] = float(msg.param_value)

                # Early exit if all expected params fetched
                if expected_count and len(fetched) >= expected_count:
                    break
            else:
                if fetched and (time.time() - last_recv_time > 0.35):
                    break

        self.vehicle_params = fetched
        print(f"[MAVLink] Fetched {len(fetched)} existing parameters from vehicle.")
        return fetched

    def upload_parameters_burst(
        self, 
        params_to_upload: Dict[str, float], 
        max_attempts: int = 3, 
        progress_callback: Optional[Callable[[str, str], None]] = None
    ) -> Tuple[List[str], List[str]]:
        """
        Pipelined Burst Mode (Mission Planner Style):
        Streams PARAM_SET messages rapidly without blocking per-parameter,
        then collects ACKs and retries missing items.
        """
        if not self.master:
            raise RuntimeError("MAVLink connection not established. Call connect() first.")

        unconfirmed = set(params_to_upload.keys())
        updated_list = []
        
        for attempt in range(1, max_attempts + 1):
            if not unconfirmed:
                break

            # Drain any stale packets sitting in socket buffer
            while self.master.recv_match(type='PARAM_VALUE', blocking=False):
                pass

            # Phase 1: Rapid-fire burst of PARAM_SET
            for param_name in list(unconfirmed):
                val = params_to_upload[param_name]
                param_id_bytes = param_name.strip().encode('ascii')[:16]
                self.master.mav.param_set_send(
                    self.master.target_system,
                    self.master.target_component,
                    param_id_bytes,
                    float(val),
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32
                )
                time.sleep(0.001)  # 1ms burst interval (Mission Planner rate)

            # Phase 2: Collect ACKs for the burst
            ack_wait_start = time.time()
            ack_timeout = 0.25 if attempt == 1 else 0.40

            while time.time() - ack_wait_start < ack_timeout:
                if not unconfirmed:
                    break
                msg = self.master.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.02)
                if msg is not None:
                    raw_id = msg.param_id
                    if isinstance(raw_id, str):
                        recv_id = raw_id.rstrip('\x00').strip().upper()
                    elif isinstance(raw_id, bytes):
                        recv_id = raw_id.rstrip(b'\x00').decode('ascii', errors='ignore').strip().upper()
                    else:
                        recv_id = str(raw_id).rstrip('\x00').strip().upper()

                    if recv_id in unconfirmed:
                        unconfirmed.remove(recv_id)
                        updated_list.append(recv_id)
                        if progress_callback:
                            progress_callback(recv_id, "OK")

        failed_list = list(unconfirmed)
        for f_param in failed_list:
            if progress_callback:
                progress_callback(f_param, "FAIL")

        return updated_list, failed_list

    def upload_parameters_dict(
        self, 
        params: Dict[str, float], 
        retries: int = 2, 
        retry_timeout: float = 0.15,
        skip_prefetch: bool = False,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Uploads a dictionary of parameters using Mission Planner's fast Diff + Burst technique.
        Returns (updated_list, skipped_list, failed_list).
        """
        if not self.master:
            self.connect()

        current_params = {}
        if not skip_prefetch:
            try:
                print("[MAVLink] Pre-fetching vehicle parameters for comparison...")
                current_params = self.fetch_all_vehicle_params(timeout=6.0)
            except Exception as e:
                print(f"[Warning] Could not pre-fetch vehicle params: {e}")
                current_params = {}
        else:
            print("[MAVLink] Direct SET Mode: Skipping pre-fetch...")

        total = len(params)
        skipped_list = []
        params_to_upload = {}

        # Step 1: Instant Diff Filtering
        for idx, (param_name, val) in enumerate(params.items(), 1):
            if current_params and param_name in current_params and abs(current_params[param_name] - float(val)) < 1e-4:
                skipped_list.append(param_name)
                if progress_callback:
                    progress_callback(idx, total, param_name, "SKIP")
            else:
                params_to_upload[param_name] = float(val)

        print(f"[MAVLink Diff] {len(skipped_list)} params match existing vehicle values (Skipped).")
        print(f"[MAVLink Diff] {len(params_to_upload)} params need updating (Streaming Burst Mode)...")

        updated_list = []
        failed_list = []

        if params_to_upload:
            def burst_callback(param_name, status):
                if progress_callback:
                    current_count = len(skipped_list) + len(updated_list) + len(failed_list) + 1
                    progress_callback(current_count, total, param_name, status)

            updated_list, failed_list = self.upload_parameters_burst(
                params_to_upload,
                max_attempts=3,
                progress_callback=burst_callback
            )

        print(f"\n[MAVLink Upload Finished] Updated: {len(updated_list)} | Skipped (Matched): {len(skipped_list)} | Failed/Unsupported: {len(failed_list)}")
        return updated_list, skipped_list, failed_list

    def close(self):
        """Closes MAVLink connection."""
        if self.master:
            self.master.close()
            print("\n[MAVLink] Connection closed.")
