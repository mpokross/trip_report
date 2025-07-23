import json
import logging
import sys
from typing import Literal, Optional, Union, Dict, Any, List
from pathlib import Path
from csv import DictReader, Error as CSVError
from box import Box

from .collect_data import SynchrotronDataCollector
from .logging_config import setup_logging
from .report_generator import IMCAReportGenerator

# Constants
JSON_FILE_NAME = 'data.json'

# Constants for CSV column names
COLUMN_PUCK = "Puck"
COLUMN_PIN = "Pin"
COLUMN_PROJECT = "Project"
COLUMN_COMMENTS = "Staff Comments"


class StrEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to convert non-serializable objects to strings.

    This encoder extends the default JSONEncoder to handle objects that
    cannot be directly serialized by converting them to their string representation.
    Useful for serializing complex objects like Path or custom classes that
    don't have a native JSON representation.
    
    Examples:
        >>> json.dumps({"path": Path("/some/path")}, cls=StrEncoder)
        '{"path": "/some/path"}'
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


def process_csv_data(csv_path: Path, result: Box, logger: logging.Logger) -> Box:
    """
    Process CSV data and update the trip data with project information.

    Args:
        csv_path: Path to the CSV file
        result: Box object containing trip data
        logger: Logger for logging messages

    Returns:
        Updated Box object with project information and csv_loaded flag.
        The csv_loaded flag is set to True if any entries from the CSV
        were successfully mapped to trip data.
    """
    if not csv_path.exists():
        logger.info(f"No CSV file found at {csv_path}")
        return result

    logger.info(f"Found CSV file at {csv_path}")

    try:
        with open(csv_path, 'r', newline='') as csvfile:
            csv_reader = DictReader(csvfile)
            csv_data = list(csv_reader)
            logger.info(f"Successfully loaded {len(csv_data)} rows from CSV file")

            # Check if expected columns exist in the CSV
            if csv_data and all(key in csv_data[0] for key in [COLUMN_PUCK, COLUMN_PIN, COLUMN_PROJECT]):
                logger.info("Mapping CSV data to trip data entries")

                # Track how many entries were matched
                matched_count = 0

                # Look for entries in the trip_data dictionary
                for row in csv_data:
                    # Check in the trip_data dictionary
                    if 'trip_data' in result:
                        for trip_key, trip_entry in result['trip_data'].items():
                            flds = trip_key.split('_')
                            try:
                                if flds[0] == row[COLUMN_PUCK] and int(flds[1]) == int(row[COLUMN_PIN]):
                                    trip_entry[0][COLUMN_PROJECT] = row[COLUMN_PROJECT]
                                    trip_entry[0][COLUMN_COMMENTS] = row[COLUMN_COMMENTS]
                                    matched_count += 1
                                    logger.debug(f"Matched {row[COLUMN_PUCK]}_{row[COLUMN_PIN]} to {trip_key}")
                                    break
                            except (ValueError, IndexError) as e:
                                # Handle cases where pin values cannot be converted or split failed
                                logger.warning(f"Could not process row {row} for key {trip_key}: {e}")
                                continue

                if matched_count > 0:
                    result['csv_loaded'] = True

                logger.info(f"Successfully mapped {matched_count} entries from CSV to trip data")
            else:
                logger.warning(
                    f"CSV file does not have the expected column format ({COLUMN_PUCK}, {COLUMN_PIN}, {COLUMN_PROJECT})")

    except (IOError, CSVError) as e:
        logger.error(f"CSV file error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error processing CSV file: {e}", exc_info=True)

    return result


def run_report(base_directory: Union[str, Path], json_flag: bool = False, debug: bool = False,
               output_pth: Optional[Union[str, Path]] = None, report_name: Optional[str] = None,
               file_method: Literal['symlink', 'copy'] = 'copy', json_file: str = JSON_FILE_NAME, no_site: bool = False,
               csv: Optional[Union[str, Path]] = None) -> None:
    """
    Generate a synchrotron trip report from either a directory or a JSON file.

    Args:
        base_directory: Path to the trip data directory or JSON file
        json_flag: If True, treat base_directory as a JSON file path
        debug: Enable debug logging if True
        output_pth: Custom output directory for the report
        report_name: Name of report file
        file_method: Method for handling files in the report ('symlink' or 'copy')
        json_file: Name of the JSON file to be generated, defaults to JSON_FILE_NAME
        no_site: If True, skip site-specific data collection
        csv: Optional path to a CSV file with additional data

    Raises:
        PermissionError: If there are permission issues accessing the directory
        FileNotFoundError: If the specified directory or file is not found
        json.JSONDecodeError: If the provided JSON file cannot be parsed
        Exception: For any unexpected errors during report generation
    """
    log_level = 'DEBUG' if debug else 'INFO'
    logger: logging.Logger = setup_logging(log_level=log_level)

    # Convert path parameters to Path objects early
    if isinstance(base_directory, str):
        base_directory = Path(base_directory)

    try:
        result = Box()
        # Read from json file or collect data from trip directory
        if json_flag:
            try:
                with open(base_directory) as json_data:
                    try:
                        result = Box.from_json(json_data.read())
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON file: {base_directory}")
                        raise
            except FileNotFoundError:
                logger.error(f"JSON file not found: {base_directory}")
                raise FileNotFoundError(f"JSON file not found: {base_directory}")
        else:
            collector = SynchrotronDataCollector(
                base_path=base_directory,
                logger=logger,
            )
            # Create a Box object from the collected data
            result: result = Box(collector.collect_data(no_site=no_site))

        if not result:
            logger.error(f"Could not collect data from {base_directory}")
            sys.exit(1)

        # Default: CSV data not loaded
        result.csv_loaded = False

        # Trip Name
        trip_name: str = result['trip_name']

        # Handle output dir creation
        report_dir_name: str = f'{trip_name}_Trip_Report' if report_name is None else report_name
        if output_pth is None:
            output_pth = Path.cwd() / report_dir_name
        else:
            output_pth = Path(output_pth) / report_dir_name
        output_pth.mkdir(parents=True, exist_ok=True)

        # Load and process CSV File if provided
        if csv is not None:
            csv_pth = Path(csv)
            result = process_csv_data(csv_pth, result, logger)
        else:
            logger.info("No CSV file specified")

        # Write json file
        json_content: str = json.dumps(result, indent=4, sort_keys=True, cls=StrEncoder)
        json_file_path: Path = output_pth / json_file
        try:
            with open(json_file_path, 'w') as f:
                f.write(json_content)
            logger.info(f"Data written to {json_file_path}")
        except IOError as e:
            logger.error(f"Failed to write JSON file: {e}")
            raise

        # Generate html report
        html_report_title: str = f'{trip_name} Trip Report'
        generator: IMCAReportGenerator = IMCAReportGenerator(result['trip_data'])
        generator.generate_reports(
            output_dir=output_pth,
            file_method=file_method,
            report_title=html_report_title,
            csv_loaded=result['csv_loaded'],
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
