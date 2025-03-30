import argparse
import sys
from typing import List
from typing import Optional

from . import run_report

# Package version
__version__ = '0.1.0'

def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for the trip report CLI.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog='trip_report', 
        description='Synchrotron Data Collector and Report Generator'
    )
    
    # Version argument
    parser.add_argument(
        '--version', 
        action='version', 
        version=f'%(prog)s {__version__}'
    )
    
    parser.add_argument(
        'base_directory',
        type=str,
        help='Base directory for synchrotron data collection (path to trip data or JSON file)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        dest='json_flag',
        default=False,
        help='Use a JSON file as input instead of a directory'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable debug logging for detailed output'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Specify output directory for the report, use --report_name to set the report name'
    )

    parser.add_argument(
        '--report-name',
        type=str,
        default=None,
        help='Specify report name'
    )
    
    parser.add_argument(
        '--file-method',
        type=str,
        choices=['copy', 'symlink'],
        default='copy',
        help='Method to use for file operations: copy or symlink files'
    )
    
    return parser

def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the trip report CLI.

    Args:
        argv (Optional[List[str]], optional): Command-line arguments. 
                                              Defaults to sys.argv[1:] if None.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    parser = create_parser()
    
    # Use provided argv or default to system arguments
    args = parser.parse_args(argv)
    
    try:
        run_report(
            base_directory=args.base_directory, 
            json_flag=args.json_flag, 
            debug=args.debug, 
            output_pth=args.output,
            report_name=args.report_name,
            file_method=args.file_method
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
