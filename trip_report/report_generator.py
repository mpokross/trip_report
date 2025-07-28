import functools
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Union, Optional

from jinja2 import Environment
from jinja2 import FileSystemLoader

from .logging_config import get_logger


class FileHandlingMethod(Enum):
    """
    Enumeration of methods for handling files during report generation.

    Defines the strategies for transferring files when creating reports:
    - SYMLINK: Create symbolic links to original files
    - COPY: Create physical copies of files
    """
    SYMLINK = "symlink"
    COPY = "copy"


@dataclass
class CameraFile:
    """
    Represents a camera file with its source and destination paths.

    Attributes:
        source_path (Path): Original location of the camera file
        relative_path (str): Relative path of the file in the generated report
    """
    source_path: Path
    relative_path: str


@dataclass
class ReportConfig:
    """
    Configuration settings for report generation.

    Attributes:
        output_dir (Path): Directory where reports will be generated
        file_method (FileHandlingMethod): Method for handling files in the report
        report_title (str): Title of the generated report
        csv_loaded (bool): Whether or not the generated report was loaded
    """
    output_dir: Path
    file_method: FileHandlingMethod
    report_title: str
    csv_loaded: bool


class IMCAReportError(Exception):
    """
    Base exception for IMCA Report Generator errors.

    Serves as a parent class for more specific report generation exceptions.
    """
    pass


class FileHandlingError(IMCAReportError):
    """
    Exception raised when file handling operations fail during report generation.

    Indicates issues with copying, symlinking, or managing files in the report.
    """
    pass


class TemplateRenderingError(IMCAReportError):
    """
    Exception raised when template rendering fails during report generation.

    Signals problems with processing Jinja2 templates or generating HTML pages.
    """
    pass


class IMCAReportGenerator:
    """
    Generates comprehensive HTML reports for IMCA (Integrated Macromolecular Crystallography Automation) data.

    Processes synchrotron data, manages file handling, and creates detailed HTML reports
    with camera files, summaries, and processing information.

    Attributes:
        logger (logging.Logger): Logger for tracking report generation events
        imca_data (Dict): Collected IMCA data to be processed
        report_root (Path): Root directory for generated reports
        template_dir (Path): Directory containing Jinja2 templates
        env (jinja2.Environment): Jinja2 template rendering environment
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initialize the report generator with collected synchrotron data.

        Args:
            data: Dictionary containing IMCA data to be processed in the report
        """
        self.logger = get_logger('imca_report.report_generator')
        self.imca_data = data
        self.report_root = Path()

        # Setup Jinja2 environment
        self.template_dir = Path(__file__).parent / 'templates'
        self.env = Environment(loader=FileSystemLoader(str(self.template_dir)))
        self.env.globals.update(now=datetime.now)

    def _find_camera_files(self, collection_path: Union[str, Path]) -> List[Path]:
        """
        Find camera files for a given collection path.

        Locates and sorts camera files (*.jpg) in the 'camera' subdirectory,
        with a specific sorting order prioritizing 'before' and 'after' images.

        Args:
            collection_path: Path to the collection directory

        Returns:
            Sorted list of camera file paths
        """
        camera_dir = Path(collection_path) / 'camera'
        if not camera_dir.exists():
            return []

        # Sort files with specific ordering
        files = list(camera_dir.glob('*.jpeg'))
        return sorted(
            files,
            key=lambda x: (
                'before' not in x.name.lower(),
                'after' not in x.name.lower(),
                str(x)
            )
        )

    def _handle_file(
            self,
            source_path: Path,
            output_dir: Path,
            filename: str,
            method: FileHandlingMethod
    ) -> str:
        """
        Handle file by either creating a symlink or copying the file.

        Args:
            source_path: Path to the source file
            output_dir: Directory to place the file
            filename: Name of the file in the output directory
            method: Method to handle the file (symlink or copy)

        Returns:
            Relative path of the file in the output directory

        Raises:
            FileHandlingError: If file handling operations fail
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        dest_path = output_dir / filename

        # Remove existing file/symlink if it exists
        if dest_path.exists():
            dest_path.unlink()

        # Handle file based on method
        try:
            if method == FileHandlingMethod.SYMLINK:
                dest_path.symlink_to(source_path)
            elif method == FileHandlingMethod.COPY:
                shutil.copy2(source_path, dest_path)
        except (OSError, PermissionError) as e:
            self.logger.error(f"Error handling file {source_path}: {e}")
            raise FileHandlingError(f"File handling error: {e}") from e

        return str(dest_path.relative_to(self.report_root))

    def _create_camera_files(
            self,
            camera_files: List[Path],
            output_path: Path,
            puck_key: str,
            method: FileHandlingMethod
    ) -> List[str]:
        """
        Create camera files in the output directory.

        Args:
            camera_files: List of original camera file paths
            output_path: Output directory path
            puck_key: Current puck key for organizing files
            method: Method to handle files (symlink or copy)

        Returns:
            List of relative file paths
        """
        camera_output_dir = output_path / 'camera' / puck_key
        handle_file_partial = functools.partial(
            self._handle_file,
            output_dir=camera_output_dir,
            method=method
        )

        return [
            handle_file_partial(source_path=file, filename=file.name)
            for file in camera_files
        ]

    def _process_summary_file(
            self,
            entry: Dict[str, Any],
            puck_key: str,
            output_path: Path,
            file_method: FileHandlingMethod
    ) -> None:
        """
        Process summary file for an entry.

        Args:
            entry: Data entry to process
            puck_key: Current puck key
            output_path: Output directory path
            file_method: Method to handle files
        """
        processing = entry.get('processing', {})
        summary_path_str = processing.get('summary_html_pth')

        if not summary_path_str:
            return

        summary_path = Path(summary_path_str)
        self.logger.info(f"Processing summary file: {summary_path}")

        if not summary_path.is_file():
            self.logger.warning(f"Summary file not found: {summary_path}")
            return

        summary_output_dir = output_path / 'summary'
        summary_filename = f'{puck_key}_summary.html'

        try:
            summary_file_path = self._handle_file(
                summary_path,
                summary_output_dir,
                summary_filename,
                file_method
            )

            entry.setdefault('summary', {})['summary_file'] = summary_file_path
            self.logger.info(f"Summary file processed: {summary_file_path}")
        except FileHandlingError as e:
            self.logger.error(f"Error processing summary file {summary_path}: {e}")

    def _process_diff_center_results(
            self,
            entry: Dict[str, Any],
            puck_key: str,
            output_path: Path,
            file_method: FileHandlingMethod
    ) -> None:
        """
        Process diff-center result files.

        Args:
            entry: Data entry to process
            puck_key: Current puck key
            output_path: Output directory path
            file_method: Method to handle files
        """
        diff_center = entry.get('diff-center', {})
        if not isinstance(diff_center, dict):
            self.logger.warning(f"Invalid diff-center for {puck_key}: not a dictionary")
            return

        result_output_dir = output_path / 'results'

        # Process ZX result
        self._process_result_file(
            diff_center,
            'imcadr-ZX-result',
            f'{puck_key}_zx_result.html',
            result_output_dir,
            file_method
        )

        # Process ZY result
        self._process_result_file(
            diff_center,
            'imcadr-ZY-result',
            f'{puck_key}_zy_result.html',
            result_output_dir,
            file_method
        )

        entry.update({'diff_center': diff_center})

    def _process_result_file(
            self,
            diff_center: Dict[str, Any],
            key: str,
            filename: str,
            output_dir: Path,
            file_method: FileHandlingMethod
    ) -> None:
        """
        Process a single result file.

        Args:
            diff_center: Diff center data dictionary
            key: Key for the result file
            filename: Output filename
            output_dir: Output directory
            file_method: Method to handle files
        """
        result_path_str = diff_center.get(key)
        if not result_path_str:
            return

        result_path = Path(result_path_str)
        if not result_path.is_file():
            return

        try:
            result_file_path = self._handle_file(
                result_path,
                output_dir,
                filename,
                file_method
            )
            diff_center[f'{key}_local'] = result_file_path
        except FileHandlingError as e:
            self.logger.error(f"Error processing result file {result_path}: {e}")

    def _process_camera_files(
            self,
            entry: Dict[str, Any],
            puck_key: str,
            output_path: Path,
            file_method: FileHandlingMethod
    ) -> None:
        """
        Process camera files for an entry.

        Args:
            entry: Data entry to process
            puck_key: Current puck key
            output_path: Output directory path
            file_method: Method to handle files
        """
        collection_path = entry.get('collection_path')
        if not collection_path:
            return

        camera_files = self._find_camera_files(collection_path)
        if not camera_files:
            return

        # Create camera files
        symlink_paths = self._create_camera_files(
            camera_files,
            output_path,
            puck_key,
            file_method
        )

        entry.setdefault('camera', {})['camera_files'] = symlink_paths

    def _process_entry(
            self,
            entry: Dict[str, Any],
            puck_key: str,
            output_path: Path,
            file_method: FileHandlingMethod
    ) -> None:
        """
        Process a single data entry.

        Args:
            entry: Data entry to process
            puck_key: Current puck key
            output_path: Output directory path
            file_method: Method to handle files
        """
        # Process camera files
        self._process_camera_files(entry, puck_key, output_path, file_method)

        # Process summary file
        self._process_summary_file(entry, puck_key, output_path, file_method)

        # Process diff-center results
        self._process_diff_center_results(entry, puck_key, output_path, file_method)

    def _render_index_page(self, config: ReportConfig) -> None:
        """
        Render the index page.

        Args:
            config: Report configuration

        Raises:
            TemplateRenderingError: If template rendering fails
        """
        try:
            index_template = self.env.get_template('index.html')
            index_html = index_template.render(
                report_title=config.report_title,
                csv_loaded=config.csv_loaded,
                imca_data=self.imca_data
            )

            with (config.output_dir / 'index.html').open('w') as f:
                f.write(index_html)
        except Exception as e:
            self.logger.error(f"Error generating index page: {e}")
            raise TemplateRenderingError(f"Index page generation failed: {e}") from e

    def _render_detail_page(
            self,
            entry: Dict[str, Any],
            puck_key: str,
            output_path: Path
    ) -> None:
        """
        Render a detail page for a single entry.

        Args:
            entry: Data entry to render
            puck_key: Current puck key
            output_path: Output directory path

        Raises:
            TemplateRenderingError: If template rendering fails
        """
        try:
            detail_template = self.env.get_template('detail.html')
            detail_html = detail_template.render(
                puck_key=puck_key,
                collection=entry.get('collection', 'Unknown'),
                pos=entry.get('pos', 'N/A'),
                collection_path=entry.get('collection_path', 'N/A'),
                summary=entry.get('summary', {}).get('summary_file', None),
                camera_files=entry.get('camera', {}).get('camera_files', []),
                diff_center=entry.get('diff-center', {}),
                processing=entry.get('processing', {}).get('autoproc_xml', {}),
                images=entry.get('images', {}),
                screen=entry.get('screen', {})
            )

            detail_filename = f'{puck_key}_{entry.get("collection", "unknown")}_details.html'
            with (output_path / detail_filename).open('w') as f:
                f.write(detail_html)
        except Exception as e:
            self.logger.error(f"Error generating detail page: {e}")
            raise TemplateRenderingError(f"Detail page generation failed: {e}") from e

    def generate_reports(
            self,
            output_dir: Union[str, Path] = 'reports',
            file_method: Literal['symlink', 'copy'] = 'copy',
            report_title: str = 'IMCA Data Summary',
            csv_loaded: bool = False,
    ) -> None:
        """
        Generate HTML reports.

        Args:
            output_dir: Directory to save generated HTML files
            file_method: Method to handle files ('symlink' or 'copy')
            report_title: Title for the report

        Raises:
            IMCAReportError: If report generation fails
        """
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        self.report_root = output_path
        output_path.mkdir(parents=True, exist_ok=True)

        # Convert string method to enum
        method = FileHandlingMethod(file_method)

        # Create configuration
        config = ReportConfig(
            output_dir=output_path,
            file_method=method,
            report_title=report_title,
            csv_loaded=csv_loaded,
        )

        # Generate index page
        self._render_index_page(config)

        # Process data and generate detail pages
        for puck_key, puck_data in self.imca_data.items():
            # Process each entry in the puck data
            for entry in puck_data:
                # Process entry files
                self._process_entry(entry, puck_key, output_path, method)
                # Render detail page
                self._render_detail_page(entry, puck_key, output_path)

        self.logger.info(f"Reports generated in {output_path}")
