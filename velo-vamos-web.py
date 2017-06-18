from flask import Flask, render_template, request
import launch_webpage

app = Flask(__name__)
spd = launch_webpage.load_latest_bixi()
@app.route('/')
def index():
    return render_template('index.html')

#@app.route('/')
#def hello_world():
#   return "Hello World"

@app.route('/send_route', methods=['POST'])
def send_route():
    print("REQUEST", request.form)
    #launch_webpage.test_launch()

    return "Launching a new tab with google maps bixi route"

@app.route("/test")
def process1():
    launch_webpage.test_launch()
    #return "Hello World"
    return "test"

if __name__ == '__main__':
   app.run()
