from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
import hashlib
import bcrypt
import os
from datetime import datetime,timedelta
from dotenv import load_dotenv
from flask_restful import Api, Resource
app = Flask(__name__)

api = Api(app)


app.permanent_session_lifetime = timedelta(minutes=30)

load_dotenv()
app.secret_key = os.getenv("SECRET_KEY")

class UserProfileAPI(Resource):
    def get(self):
        if 'username' not in session:
            return {"error": "Unauthorized"}, 401

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT username, email FROM users WHERE username = %s", (session['username'],))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user:
            return {"username": user[0], "email": user[1]}, 200
        return {"error": "User not found"}, 404

api.add_resource(UserProfileAPI, '/api/profile')

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        auth_plugin="mysql_native_password"
    )


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        weight = request.form['weight']
        height = request.form['height']
        age = request.form['age']

        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash("Username already exists! Choose a different one.", "error")
            return render_template('sign_up.html')

        cursor.execute("INSERT INTO users (username, password, email, weight, height, age) VALUES (%s, %s, %s, %s, %s, %s)", 
                       (username, hashed_password, email, weight, height, age))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Sign up successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('sign_up.html')


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        session.permanent=True  
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user and bcrypt.checkpw(password.encode(), user[1].encode()):
            session['username'] = username
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials!", "error")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT workout_name, description, duration, intensity, date, category, calories_burned FROM workouts WHERE username = %s", (session['username'],))
    workouts = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template('dashboard.html', workouts=workouts)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))  
    
    username = session['username']
    connection = get_db_connection()
    cursor = connection.cursor()
    
   
    cursor.execute("SELECT username, email, weight, height, age, created_at FROM users WHERE username = %s", (username,))
    user = cursor.fetchone() 
    
    if user:
        user = {
            'username': user[0],
            'email': user[1],
            'weight': user[2],
            'height': user[3],
            'age': user[4],
            'created_at': user[5].strftime('%Y-%m-%d %H:%M:%S') if user[5] else None
        }

    cursor.close()
    connection.close()

    return render_template('profile.html', user=user)




@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login')) 

    username = session['username']
    
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT username, email, weight, height, age FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if not user:
        flash("User not found!", "error")
        return redirect(url_for('dashboard')) 
    if request.method == 'POST':
        new_email = request.form['email']
        new_weight = request.form['weight']
        new_height = request.form['height']
        new_age = request.form['age']
        new_password = request.form['password']

     
        new_password_hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()


        cursor.execute(
            "UPDATE users SET email = %s, weight = %s, height = %s, age = %s, password = %s WHERE username = %s",
            (new_email, new_weight, new_height, new_age, new_password_hashed, username)
        )
        connection.commit()

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))


    cursor.close()
    connection.close()

    return render_template('edit_profile.html', user=user)



MET_VALUES = {
    'low': 3,        
    'medium': 6,     
    'high': 10     
}


@app.route('/add_workout', methods=['GET', 'POST'])
def add_workout():
    if 'username' not in session:
        flash("You must be logged in to add a workout.", "error")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = session['username']
        workout_name = request.form['workout_name']
        description = request.form['description']
        duration = request.form['duration']
        intensity = request.form['intensity']
        category = request.form['category']
        date = request.form['date']  
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date() 
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for('add_workout'))

       
        try:
            duration = float(duration) 
        except ValueError:
            flash("Invalid duration value. Please enter a valid number.", "error")
            return redirect(url_for('add_workout'))

        
        duration_in_hours = duration / 60

        if intensity.lower() not in MET_VALUES:
            flash("Invalid intensity value!", "error")
            return redirect(url_for('add_workout'))


        user_weight_kg = 70  

        met_value = MET_VALUES[intensity.lower()]
        calories_burned = met_value * user_weight_kg * duration_in_hours

        
        connection = get_db_connection()
        cursor = connection.cursor()

        
        query = """
            INSERT INTO workouts (username, workout_name, description, duration, intensity, date, category, calories_burned)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (username, workout_name, description, duration, intensity, date, category, calories_burned)
        cursor.execute(query, values)
        connection.commit()

        flash("Workout added successfully!", "success")
        return redirect(url_for('dashboard'))  
    
    from datetime import date
    today = date.today()
    return render_template('add_workout.html', today=today)


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    app.run(debug=True)
