from app import app, db
from app.models import User, Post, Comment
from flask import jsonify, render_template, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required


def check_data(data):
    if not data:
        return jsonify({'error': 'No input data provided'}), 400


def register():
    """Register a new user"""
    data = request.get_json()
    check_data(data)

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({'error': 'Username, email, and password are required'}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({'error': 'Username or email already exists'}), 400

    user = User(username=username, email=email, password=password) # type: ignore
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created successfully"}), 201


@app.route('/login', methods=["POST"])
def login():
    """Login user"""
    if current_user.is_appenticated:
        return jsonify({"message": "You are already logged in"}), 200
        
    data = request.get_json()
    check_data(data)

    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if user and user.verify_password(password):
        login_user(user)
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(url_for(next_page))
        return jsonify({"message": "Login successful", "user": user.to_dict()}), 200
    
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/logout', methods=["POST"])
@login_required
def logout():
    """Logout user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200


app.route('/profile')
@login_required
def profile():
    user = current_user
    return jsonify(
        {
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'posts': [post for post in user.posts],
            'user_id': user.id
        }
    )