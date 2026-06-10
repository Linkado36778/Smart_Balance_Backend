# Smart Balance Backend
Backend of the Smart Balance developed as a Capstone project for university, UNISANTA. 

## Minimum System Requirements

- Git
- Python 3.14+
- PostgreSQL

## Quick Start

Set up the application on your computer in 6 steps:

1. Create a `.env` file in the root folder of the application with the following information 

```properties
SQLALCHEMY_DATABASE_URL="postgresql://<your_user>:<your_password>@<host>:<port>/<database_name>"
```

2. Create a python virtual environment: `python -m venv .venv`.
3. Activate the virtual environment using `source .venv/bin/activate` (on Linux/Mac) or just `.venv\Scripts\activate` (on Windows).
4. Install the dependencies running `pip install -r requirements.txt`.
5. Run `python main.py` to create the database.
6. Start the application using `fastapi run main.py`.