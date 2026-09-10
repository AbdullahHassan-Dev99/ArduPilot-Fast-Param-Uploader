"""
Main CLI Script: Parameter Loader & Converter for Mission Planner / ArduPilot
"""

import argparse
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import param_parser
from param_uploader import MavParamUploader

def print_banner():
    banner = r"""
===========================================================
  ArduPilot / Mission Planner Parameter Loader & Converter
===========================================================
    """
    print(banner)

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Load .param or .json parameter files onto Mission Planner / ArduPilot.")
    parser.add_argument("-f", "--file", type=str, help="Path to input parameter file (.param, .params, .json)")
    parser.add_argument("-c", "--connect", type=str, default="udpout:127.0.0.1:14551", help="MAVLink connection string (e.g. udpin:0.0.0.0:14551, tcp:127.0.0.1:5760, tcp:127.0.0.1:5762)")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="Baud rate for serial connections (default: 115200)")
    parser.add_argument("--convert", type=str, choices=['json', 'param'], help="Convert input file format to 'json' or 'param'")
    parser.add_argument("-o", "--output", type=str, help="Output path for converted parameter file")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate parameter file without connecting to vehicle")
    parser.add_argument("--force-all", action="store_true", help="Bypass Mission Planner smart pre-fetch and force upload all parameters directly")

    args = parser.parse_args()

    filepath = args.file
    if not filepath:
        default_file = r"C:\Users\asus\Desktop\plane 2\komodony FINAL 13-5.param"
        if os.path.exists(default_file):
            filepath = default_file
        else:
            filepath = input("Enter path to parameter file (.param or .json) [Default: EAGLES PARAMS.param]: ").strip()
            if not filepath:
                filepath = "EAGLES PARAMS.param"

    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    print(f"[1/3] Parsing parameter file: '{filepath}'...")
    try:
        params = param_parser.load_parameters(filepath)
        print(f"      Successfully loaded {len(params)} parameters.")
    except Exception as e:
        print(f"Error loading parameter file: {e}")
        sys.exit(1)

    # Conversion mode
    if args.convert:
        out_path = args.output
        if not out_path:
            base_name = os.path.splitext(filepath)[0]
            out_path = f"{base_name}_converted.{args.convert}"
        
        print(f"\n[Converting] Saving parameters to {args.convert.upper()} format at '{out_path}'...")
        if args.convert == 'json':
            param_parser.save_to_json_file(params, out_path)
        else:
            param_parser.save_to_param_file(params, out_path)
        print("Conversion finished successfully!")
        if args.dry_run:
            return

    if args.dry_run:
        print("\n[Dry Run] Validation successful. Exiting without MAVLink connection.")
        return

    # MAVLink Upload mode
    connection_str = args.connect
    baud_rate = args.baud

    print(f"\n[2/3] Preparing MAVLink upload to '{connection_str}'...")
    uploader = MavParamUploader(connection_string=connection_str, baud=baud_rate)

    try:
        uploader.connect()
    except Exception as e:
        print(f"\n[Connection Failed] {e}")
        sys.exit(1)

    print(f"\n[3/3] Uploading {len(params)} parameters...")
    
    def cli_progress(idx, total, param_name, status_code):
        percent = (idx / total) * 100
        bar_length = 30
        filled = int(bar_length * idx // total)
        bar = '#' * filled + '-' * (bar_length - filled)
        try:
            sys.stdout.write(f"\r[{bar}] {percent:5.1f}% ({idx}/{total}) {param_name[:15]:<15} [{status_code:<4}]")
            sys.stdout.flush()
        except Exception:
            pass

    updated_list, skipped_list, failed_list = uploader.upload_parameters_dict(params, skip_prefetch=args.force_all, progress_callback=cli_progress)
    uploader.close()

    print("\n\n===========================================================")
    print("                UPLOAD SUMMARY REPORT                      ")
    print("===========================================================")
    print(f" Total Parameters Processed : {len(params)}")
    print(f" Successfully Updated      : {len(updated_list)}")
    print(f" Skipped (Already Matched) : {len(skipped_list)}")
    print(f" Failed / Unsupported      : {len(failed_list)}")
    if updated_list:
        print(f"\n Updated Parameters List    : {updated_list}")
    if failed_list:
        print(f"\n Note: Failed parameters are usually hardware-specific")
        print(f" or unsupported by the current vehicle firmware version.")
        print(f" Sample Failed List        : {failed_list[:10]}")
    print("===========================================================\n")

if __name__ == "__main__":
    main()
