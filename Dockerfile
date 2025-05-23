# Use the official Python image as the base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
RUN pip install --no-cache-dir -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple gunicorn uvicorn

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
#CMD ["python", "main.py","--multiprocess"]
# 生产环境使用gunicorn启动多进程
CMD ["gunicorn", "main:app", "-w", "12", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]