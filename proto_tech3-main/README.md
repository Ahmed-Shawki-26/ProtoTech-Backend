# FastAPI PCB Renderer API

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.103.2-blueviolet)](https://fastapi.tiangolo.com/)
[![pcb-tools-fork](https://img.shields.io/badge/pcb--tools--fork-2.8.0-orange)](https://pypi.org/project/pcb-tools-fork/)

A robust, high-performance web service for rendering beautiful, high-quality images of Printed Circuit Boards (PCBs) from Gerber files. This API accepts a `.zip` archive of Gerber and Excellon files, processes them, and returns a new `.zip` file containing:

-   `pcb_top.png`: A themed, high-resolution image of the top side of the PCB.
-   `pcb_bottom.png`: A themed, high-resolution image of the bottom side of the PCB.
-   `dimensions.json`: A file containing the calculated physical width, height, and area of the board.

## Features

-   **Easy to Use**: Single endpoint to upload a ZIP and get a fully rendered package back.
-   **High-Quality Rendering**: Uses `pcb-tools-fork` and `cairocffi` to generate crisp, anti-aliased images.
-   **Themed Output**: Comes with a pre-configured "Mustard Yellow" theme for visually appealing results. Easily extendable with more themes.
-   **Automatic Dimension Calculation**: Intelligently finds the board outline layer to calculate width (mm), height (mm), and area (cm²).
-   **Robust Error Handling**: Provides clear feedback for invalid ZIP files or unparseable Gerber layers.
-   **Modern Tech Stack**: Built with FastAPI for high performance and automatic interactive documentation.
-   **Scalable Architecture**: The project is structured with a clear separation of concerns (API, services, schemas) to make it easy to maintain and extend.

## API Endpoint

### `POST /api/v1/render-pcb/`

This is the main endpoint for processing Gerber files.

-   **Request Body**: `multipart/form-data` containing a single file.
    -   `file`: The `.zip` archive containing your Gerber and Excellon files.
-   **Successful Response (200 OK)**:
    -   **Content-Type**: `application/zip`
    -   **Body**: A new ZIP file named `rendered_<original_filename>.zip` containing the rendered PNG images and `dimensions.json`.
-   **Error Responses**:
    -   `400 Bad Request`: If the uploaded file is not a valid ZIP, or if no valid Gerber layers are found inside.
    -   `500 Internal Server Error`: For any unexpected processing errors.

## Getting Started

### Prerequisites

-   Python 3.9+
-   `pip` for package installation.
-   Some system dependencies for `cairocffi`. On Debian/Ubuntu, you can install them with:
    ```bash
    sudo apt-get update && sudo apt-get install -y libcairo2-dev libffi-dev
    ```

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-directory>
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate
    # On Windows, use: venv\Scripts\activate
    ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

### Creating `requirements.txt`

Create a file named `requirements.txt` in the root of your project with the following content:

```
fastapi
uvicorn[standard]
pcb-tools-fork>=2.8.0
cairocffi
pydantic
python-multipart
```

### Running the Application

Once the installation is complete, you can run the web server using Uvicorn:

```bash
uvicorn main:app --reload
```

The API will now be running and available at `http://127.0.0.1:8000`.

-   `--reload`: Enables auto-reload, so the server will restart automatically when you make changes to the code.

## How to Use

The easiest way to interact with the API is through the automatic interactive documentation provided by FastAPI.

1.  **Start the server** as described above.
2.  **Open your web browser** and navigate to **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**.
3.  Click on the `POST /api/v1/render-pcb/` endpoint to expand it.
4.  Click the **"Try it out"** button.
5.  Under the `file` parameter, click **"Choose File"** and select a `.zip` file containing your Gerber project.
6.  Click the **"Execute"** button.
7.  The API will process the file, and your browser will prompt you to download the resulting `.zip` archive.

## Project Structure

The project follows a modern, scalable structure to ensure maintainability:

```
.
├── app/                  # Main application package
│   ├── api/              # API layer (endpoints)
│   ├── core/             # Core components (config)
│   ├── schemas/          # Pydantic data models
│   ├── services/         # Business logic
│   └── utils/            # Utility functions
├── main.py               # Main FastAPI app entrypoint
└── README.md             # This file
```

## Customization

### Changing the Theme

The default rendering theme is set to `"Blue"`. You can easily change this by modifying the `theme_to_use` variable in `app/services/gerber_processor.py`.

To create new themes, edit the `THEMES` dictionary in the `gerber/render/theme.py` file within your installed `pcb-tools-fork` library, or create a local copy and adjust the import path.

---