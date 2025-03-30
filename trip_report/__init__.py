import json
from typing import Literal, Optional, Union, Dict, Any
from pathlib import Path
import logging

from .collect_data import SynchrotronDataCollector
from .logging_config import setup_logging
from .report_generator import IMCAReportGenerator


class StrEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to convert non-serializable objects to strings.

    This encoder extends the default JSONEncoder to handle objects that 
    cannot be directly serialized by converting them to their string representation.
    """

    def default(self, obj: object) -> str:
        """
        Convert non-serializable objects to strings.

        Args:
            obj: Object to be converted to a string

        Returns:
            str: String representation of the object
        """
        return str(obj)


def run_report(
        base_directory: Union[str, Path],
        json_flag: bool = False,
        debug: bool = False,
        output_pth: Optional[Union[str, Path]] = None,
        report_name: Optional[str] = None,
        file_method: Literal['symlink', 'copy'] = 'copy',
        json_file: str = 'data.json'
) -> None:
    """
    Generate a synchrotron trip report from either a directory or a JSON file.

    Args:
        base_directory: Path to the trip data directory or JSON file
        json_flag: If True, treat base_directory as a JSON file path
        debug: Enable debug logging if True
        output_pth: Custom output directory for the report
        report_name: Name of report file
        file_method: Method for handling files in the report ('symlink' or 'copy')
        json_file: Name of the JSON file to be generated

    Raises:
        PermissionError: If there are permission issues accessing the directory
        FileNotFoundError: If the specified directory or file is not found
        Exception: For any unexpected errors during report generation
    """
    log_level = 'DEBUG' if debug else 'INFO'
    logger = setup_logging(log_level=log_level)

    try:
        # Read from json file or collect data from trip directory
        if json_flag:
            with open(base_directory) as json_data:
                result: Dict[str, Any] = json.load(json_data)
        else:
            collector = SynchrotronDataCollector(
                base_path=Path(base_directory),
                logger=logger
            )
            result = collector.collect_data()

        # Trip Name
        trip_name: str = result['trip_name']

        # Handle output dir creation
        report_name: str = f'{trip_name}_Trip_Report' if report_name is None else report_name
        if output_pth is None:
            output_pth = Path.cwd() / report_name
        else:
            output_pth = Path(output_pth) / report_name
        output_pth.mkdir(parents=True, exist_ok=True)

        # Write json file
        _json: str = json.dumps(result, indent=4, sort_keys=True, cls=StrEncoder)
        json_file_path: Path = output_pth / json_file
        with open(json_file_path, 'w') as f:
            f.write(_json)
        logger.info(f"Data written to {json_file_path}")

        # Generate html report
        report_name: str = f'{trip_name} Trip Report'
        generator = IMCAReportGenerator(result['trip_data'])
        generator.generate_reports(
            output_dir=output_pth,
            file_method=file_method,
            report_title=report_name
        )

    except PermissionError:
        logger.error(f"Permission denied accessing {base_directory}")
        raise
    except FileNotFoundError:
        logger.error(f"Directory not found: {base_directory}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
