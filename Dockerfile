FROM python:3.13

WORKDIR /code

# Gradio aur pinger ke liye requirements
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . .

# Gradio app start hone ke saath pinger bhi chalega
CMD ["sh", "-c", "python pinger.py & gradio app.py"]
