# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# pipenv is needed to manage dependencies defined in Pipfile and Pipfile.lock
RUN pip install pipenv

# Copy the Pipfile and Pipfile.lock into the working directory
#COPY Pipfile . 
#COPY Pipfile.lock . 
# The '*' ensures both Pipfile and Pipfile.lock are copied

# Install dependencies using pipenv
# --system flag installs packages directly into the global site-packages 
# (which is better for Docker images than creating a virtual environment inside the container)
#RUN pipenv install --system --deploy --no-cache-dir
#Couldn't get pipenv to work; kept getting error: See also : {} --deploy flag so using requirements.txt for now

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Define the command to run your application when the container starts
CMD ["python", "app.py"]
