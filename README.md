# Trip Report Generator

## Overview
A robust Python application for generating comprehensive HTML reports from synchrotron data collection. Transforms complex crystallography data into readable, structured HTML reports with enhanced type safety, detailed documentation, and flexible processing capabilities.

## Key Features
- Advanced data processing for synchrotron experiments
- Comprehensive HTML report generation
- Robust error handling and logging
- Support for multiple data formats (XML, H5, CBF, JPG)
- Responsive and mobile-friendly report design
- Enhanced type safety and code quality

## Technical Highlights
- Comprehensive type hinting
- Detailed docstrings for all classes and methods
- Flexible file handling (symlink and copy modes)
- Configurable logging
- Modular and extensible architecture

## Requirements
- Python 3.8+
- Jinja2
- xmltodict
- python-box
- typing_extensions (optional)

## Installation
1. Ensure Python 3.8+ is installed
2. Clone the repository
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
```bash
# Basic usage
python -m trip_report /path/to/synchrotron/data

# Advanced options
python -m trip_report /path/to/synchrotron/data --debug --output ./reports
```

### Command Line Options
- `--version`: Display package version
- `--json`: Switch input to JSON file
- `--debug`: Enable detailed debug logging
- `--output`: Specify custom output directory
- `--file-method`: Choose file handling method (copy or symlink)

## Report Structure
- `index.html`: Comprehensive summary of all data collections
- `{puck_key}_details.html`: Detailed information for each collection
- Organized file directories for camera images, summaries, and results

## Customization
- Modify HTML templates in `templates/`
- Adjust report generation logic in `report_generator.py`
- Extend data processing capabilities in `collect_data.py`

## Development Highlights
- Extensive type annotations
- Comprehensive error handling
- Modular design with clear separation of concerns
- Configurable logging system
- Flexible data processing architecture

## Performance Considerations
- Efficient file handling with symlink and copy options
- Optimized XML parsing
- Minimal memory overhead
- Scalable design for large datasets

## Troubleshooting
- Verify Python version (3.8+)
- Ensure all dependencies are installed
- Check input data structure
- Use `--debug` flag for detailed logging

## Contributing
Contributions are welcome! 

Guidelines:
- Follow PEP 8 style guidelines
- Add type hints for new code
- Write comprehensive docstrings
- Include unit tests for new features
- Submit pull requests with detailed descriptions

## License
MIT License

## Future Roadmap
- Implement more comprehensive unit tests
- Add configuration file support
- Enhance performance optimizations
- Expand logging capabilities
- Support additional data formats