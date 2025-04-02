import logging
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, DefaultDict

import xmltodict
from box import Box

from .logging_config import get_logger


# Constants and configuration
class DirectoryType(Enum):
    CAMERA = "camera"
    IMAGES = "images"
    PROCESSING = "processing"
    DIFF_CENTER = "diff-center"
    DIFF_CENTER2 = "diff-center2"
    SCREEN = "screen"


# Mapping for scaling statistics fields
SCALING_STATISTICS_DICT = {
    "scalingstatisticstype": "Scaling Statistics Type",
    "resolutionlimitlow": "Resolution Limit Low",
    "resolutionlimithigh": "Resolution Limit High",
    "rmerge": "RMerge",
    "rmeaswithiniplusiminus": "RMeas Within IPlus IMinus",
    "rmeasalliplusiminus": "RMeas All IPlus IMinus",
    "rpimwithiniplusiminus": "RPim Within IPlus IMinus",
    "rpimalliplusiminus": "RPim All IPlus IMinus",
    "ntotalobservations": "N Total Observations",
    "ntotaluniqueobservations": "N Total Unique Observations",
    "meanioversigi": "Mean I Over SigI",
    "completeness": "Completeness",
    "multiplicity": "Multiplicity",
    "cchalf": "CC Half",
    "anomalouscompleteness": "Anomalous Completeness",
    "anomalousmultiplicity": "Anomalous Multiplicity",
    "ccanomalous": "CC Anomalous",
    "danooversigdanotool": "DAno Over SigDAno Tool"
}


@dataclass
class ProcessingStats:
    """Statistics for data processing operations"""
    total_pucks: int = 0
    processed_pucks: int = 0
    skipped_pucks: int = 0
    total_collections: int = 0
    processed_collections: int = 0
    skipped_collections: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)


class SynchrotronDataProcessingError(Exception):
    """Custom exception for synchrotron data processing errors."""
    pass


class XmlParsingError(SynchrotronDataProcessingError):
    """Exception for XML parsing errors."""
    pass


class SynchrotronDataCollector:
    """
    A class to collect and process synchrotron data from a given directory structure.

    Expected directory structure:
    base_path/
    ├── site1/
    │   ├── puck1/
    │   │   ├── position1/
    │   │   │   ├── collection1/
    │   │   │   │   ├── camera/
    │   │   │   │   ├── images/
    │   │   │   │   └── processing/
    │   │   │   └── collection2/
    │   │   └── position2/
    │   └── puck2/
    └── site2/

    Each directory type (camera, images, processing, etc.) is processed
    differently to extract relevant information.
    """

    def __init__(self, base_path: Union[str, Path], logger: Optional[logging.Logger] = None):
        """
        Initialize the data collector.

        Args:
            base_path: Root directory for data collection
            logger: Optional logger instance
        """
        self.base_path = Path(base_path)
        self.logger = logger or get_logger('imca_report.collect_data')
        self.trip_data: DefaultDict[str, List[Any]] = defaultdict(list)

    @staticmethod
    def find_files(directory: Path, ext: str) -> List[Path]:
        """Find files with specified extension in a directory."""
        return list(directory.glob(f'*.{ext}'))

    def find_file(self, pth: Path) -> Optional[Path]:
        """
        Find a file at the given path.

        Args:
            pth: Path to the file to find

        Returns:
            Path to the file if it exists, None otherwise
        """
        if pth.exists():
            return pth

        self.logger.debug(f"File not found: {pth}")
        return None

    def extract_tar(self, tar_path: Path) -> None:
        """
        Safely extract tar files with logging.

        Args:
            tar_path: Path to tar file
        """
        try:
            with tarfile.open(tar_path, 'r:*') as tar:
                self.logger.info(f"Extracting compressed file: {tar_path.name}")
                tar.extractall(path=tar_path.parent)
        except Exception as e:
            self.logger.error(f"Tar extraction failed for {tar_path}: {e}")

    def process_directory(self, directory: Path) -> Dict:
        """
        Process specific directories and extract relevant information.

        Args:
            directory: Directory to process

        Returns:
            Dictionary of extracted information
        """
        directory_processors = {
            DirectoryType.CAMERA.value: self._process_camera_directory,
            DirectoryType.IMAGES.value: self._process_images_directory,
            DirectoryType.PROCESSING.value: self._process_processing_directory,
            DirectoryType.DIFF_CENTER.value: self._process_diff_center_directory,
            DirectoryType.DIFF_CENTER2.value: self._process_diff_center2_directory,
            DirectoryType.SCREEN.value: self._process_screen_directory
        }

        processor = directory_processors.get(directory.name)

        if processor:
            result = processor(directory)
            self.logger.debug(f"Processed {directory.name} directory: {result}")
            return {directory.name: result}

        return {}

    def _read_xml_file(self, file_path: Path) -> str:
        """
        Read XML file with multiple encoding fallbacks.

        Args:
            file_path: Path to XML file

        Returns:
            XML content as string

        Raises:
            XmlParsingError: If file cannot be read
        """
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                return file_path.read_text(encoding='latin-1')
            except Exception as e:
                raise XmlParsingError(f"Failed to read XML file: {e}")

    def _parse_xml_content(self, xml_content: str) -> Dict:
        """
        Parse XML content to dictionary.

        Args:
            xml_content: XML content as string

        Returns:
            Parsed XML as dictionary

        Raises:
            XmlParsingError: If XML parsing fails
        """
        try:
            return Box(xmltodict.parse(xml_content, dict_constructor=dict))
        except (ValueError, TypeError) as xml_err:
            raise XmlParsingError(f"XML parsing error: {xml_err}")

    def _extract_autoproc_data(self, auto_proc_container: Dict) -> Dict:
        """
        Extract AutoProc data from parsed XML.

        Args:
            autoproc: Parsed AutoProc XML

        Returns:
            Extracted data dictionary
        """
        results = {}

        # Extract AutoProc data
        data = auto_proc_container.get('AutoProc', {})
        cell_data = {}
        new_data = {}
        for key, value in data.items():
            if 'Cell' in key:
                parts = key.split('_')
                cell_data[parts[1].upper()] = f'{float(value):.2f}'
            else:
                new_data[key] = value

        new_data['cell_data'] = cell_data

        results.update(new_data)

        return results

    def _extract_scaling_statistics(self, auto_proc_container: Dict) -> Dict:
        """
        Extract scaling statistics from AutoProc container.

        Args:
            auto_proc_container: AutoProc container dictionary

        Returns:
            Extracted scaling statistics
        """
        results = {}
        scaling_container = auto_proc_container.get('AutoProcScalingContainer', {})
        scaling_stats = scaling_container.get('AutoProcScalingStatistics', [])

        if scaling_stats and isinstance(scaling_stats, list):
            stats = scaling_stats[0] if scaling_stats else {}
            new_stats = {}
            for key, value in stats.items():
                new_key = SCALING_STATISTICS_DICT.get(key.lower())
                if new_key:
                    new_stats[new_key] = value
                else:
                    new_stats[key] = value
            results.update(new_stats)

        return results

    def _process_autoproc_xml(self, file_path: Path) -> Dict:
        """
        Process AutoProc XML file with robust error handling.

        Args:
            file_path: Path to the AutoProc XML file

        Returns:
            Dictionary of extracted AutoProc information
        """
        # Strict input validation
        if not isinstance(file_path, Path):
            self.logger.error(f"Invalid input type: Expected Path, got {type(file_path)}")
            return {}

        if not file_path.is_file():
            self.logger.warning(f"XML file not found: {file_path}")
            return {}

        try:
            # Read and parse XML
            xml_content = self._read_xml_file(file_path)

            if not xml_content.strip():
                self.logger.warning(f"Empty XML file: {file_path}")
                return {}

            autoproc = self._parse_xml_content(xml_content)
            auto_proc_container = autoproc.get('AutoProcContainer', {})

            # Extract data
            results = self._extract_autoproc_data(auto_proc_container)
            results['scale_data'] = (self._extract_scaling_statistics(auto_proc_container))

            return results

        except XmlParsingError as e:
            self.logger.error(f"{e}")
            return {}
        except Exception as unexpected_err:
            self.logger.error(f"Unexpected XML processing error: {unexpected_err}")
            return {}

    def _process_camera_directory(self, directory: Path) -> Dict:
        """Process camera directory."""
        return {'camera_files': self.find_files(directory, 'jpg')}

    def _process_images_directory(self, directory: Path) -> Dict:
        """Process images directory."""
        images = self.find_files(directory, 'h5') or self.find_files(directory, 'cbf')
        return {
            'images_path': directory,
            'num_images': len(images)
        }

    def _process_screen_directory(self, directory: Path) -> Dict:
        images = self.find_files(directory, 'h5') or self.find_files(directory, 'cbf')
        return {
            'images_path': directory,
            'num_images': len(images)
        }

    def _process_processing_directory(self, directory: Path) -> Dict:
        """
        Process the processing directory for specific files.

        Args:
            directory: Processing directory

        Returns:
            Dictionary of processing files
        """
        summary_html = directory / 'summary.html'
        autoproc_xml = directory / 'autoPROC.xml'

        return {
            'processing_path': directory,
            'summary_html_pth': summary_html,
            'autoproc_xml_pth': autoproc_xml,
            'autoproc_xml': self._process_autoproc_xml(autoproc_xml)
        }

    def _process_diff_center_directory(self, directory: Path) -> Dict:
        """
        Generic diff center directory processor

        Args:
            directory: Path to the diff center directory

        Returns:
            Dictionary of diff center information
        """
        images = self.find_files(directory, 'h5') or self.find_files(directory, 'cbf')

        return {
            'diff_center_path': directory,
            'diff_center_files': images,
            'imcadr-ZX-result': self.find_file(directory / 'imcadr-ZX-result.html'),
            'imcadr-ZY-result': self.find_file(directory / 'imcadr-ZY-result.html')
        }

    def _process_diff_center2_directory(self, directory: Path) -> Dict:
        """Process diff-center2 directory."""
        return self._process_diff_center_directory(directory)

    def _process_collection(self, collection_path: Path, stats: ProcessingStats) -> Optional[Box]:
        """
        Process a single collection directory.

        Args:
            collection_path: Path to collection directory
            stats: Processing statistics to update

        Returns:
            Box with collection data or None if processing failed
        """
        if not collection_path.is_dir():
            return None

        puck_name = collection_path.parent.parent.name
        pos_name = collection_path.parent.name

        dataset = Box({
            'puck': puck_name,
            'pos': pos_name,
            'collection': collection_path.name,
            'collection_path': collection_path
        })

        # Process collection content
        collection_processed = False
        for child_path in collection_path.iterdir():
            try:
                if child_path.is_dir():
                    child_result = self.process_directory(child_path)
                    if child_result:
                        dataset.update(child_result)
                        collection_processed = True
            except Exception as child_err:
                stats.errors.append({
                    'path': str(child_path),
                    'error': str(child_err)
                })
                self.logger.warning(f"Error processing {child_path}: {child_err}")

        if collection_processed:
            stats.processed_collections += 1
            return dataset
        else:
            stats.skipped_collections += 1
            return None

    def _process_position(self, pos_path: Path, stats: ProcessingStats) -> None:
        """
        Process a position directory.

        Args:
            pos_path: Path to position directory
            stats: Processing statistics to update
        """
        if not pos_path.is_dir():
            stats.skipped_collections += 1
            return

        puck_name = pos_path.parent.name
        pos_name = pos_path.name
        key = f'{puck_name}_{pos_name}'

        for collection_path in pos_path.iterdir():
            if not collection_path.is_dir():
                continue

            stats.total_collections += 1
            self.logger.info(f"Processing collection: {collection_path}")

            dataset = self._process_collection(collection_path, stats)
            if dataset:
                self.trip_data[key].append(dataset)

    def _process_puck(self, puck_path: Path, stats: ProcessingStats) -> None:

        """
        Process a puck directory containing position directories.

        Args:
            puck_path: Path to the puck directory
            stats: Processing statistics to update

        Raises:
            Exception: If processing of the puck fails
        """
        if not puck_path.is_dir():
            self.logger.warning(f"Skipping {puck_path}, not a directory")
            return

        self.logger.info(f"Processing puck: {puck_path.name}")

        # Extract any tar files if present
        for tar_file in puck_path.glob("*.tar*"):
            self.extract_tar(tar_file)

        # Process each position in the puck
        position_count = 0
        for pos_path in puck_path.iterdir():
            if not pos_path.is_dir():
                continue

            position_count += 1
            try:
                self._process_position(pos_path, stats)
            except Exception as e:
                self.logger.error(f"Error processing position {pos_path.name}: {e}")
                stats.errors.append({
                    'path': str(pos_path),
                    'error': str(e)
                })

        if position_count == 0:
            self.logger.warning(f"No position directories found in puck: {puck_path.name}")

    def _process_site(self, site_path: Path, stats: ProcessingStats) -> None:
        """Process a site directory containing pucks."""
        if site_path.is_file():
            self.logger.info(f"Skipping {site_path}, not a directory")
            return

        for puck_path in site_path.iterdir():
            if not puck_path.is_dir():
                continue

            stats.total_pucks += 1
            try:
                self._process_puck(puck_path, stats)
                stats.processed_pucks += 1
            except Exception as pos_err:
                stats.skipped_pucks += 1
                stats.errors.append({
                    'path': str(puck_path),
                    'error': str(pos_err)
                })
                self.logger.error(f"Error processing puck path {puck_path}: {pos_err}")

    def collect_data(self) -> Dict:
        """
        Collect synchrotron data from directory structure with enhanced error handling.

        Returns:
            Collected data dictionary with detailed processing information

        Raises:
            SynchrotronDataProcessingError: If data collection fails
        """
        self.logger.info(f"Starting data collection from: {self.base_path}")

        # Validate base path
        if not self.base_path.is_dir():
            error_msg = f"Invalid base path: {self.base_path}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        trip_name = self.base_path.name
        stats = ProcessingStats()

        try:
            for site_path in self.base_path.iterdir():

                self._process_site(site_path, stats)



            # Log processing summary
            self.logger.info(f"Data collection summary: {stats}")
            self.logger.info(f"Data collection completed. Total Samples: {len(self.trip_data)}")

            return {
                'trip_name': trip_name,
                'trip_data': self.trip_data,
                'processing_stats': vars(stats)
            }

        except Exception as e:
            self.logger.critical(f"Critical data collection error: {e}", exc_info=True)
            stats.errors.append({
                'path': str(self.base_path),
                'error': str(e)
            })
            raise SynchrotronDataProcessingError(f"Data collection failed: {e}") from e
