from app import app, db
from app.models import User, Post, Comment
from flask import jsonify, render_template, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
import os
from werkzeug.utils import secure_filename


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def check_data(data):
    if not data:
        return jsonify({'error': 'No input data provided'}), 400


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/register', methods=["POST"])
def register():
    """Register a new user"""
    data = request.get_json()
    check_data(data)

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')

    if not all([username, email, password, name]):
        return jsonify({'error': 'Username, name, email, and password are required'}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({'error': 'Username or email already exists'}), 400

    user = User(username=username, email=email, name=name) # type: ignore
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created successfully"}), 201


@app.route('/login', methods=["POST"])
def login():
    """Login user"""
    if current_user.is_authenticated:
        return jsonify({"message": "You are already logged in"}), 200
        
    data = request.get_json()
    check_data(data)

    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if user and user.verify_password(password):
        login_user(user)
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(url_for(next_page))
        return jsonify({"message": "Login successful", "user_id": user.id}), 200
    
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/logout', methods=["POST"])
@login_required
def logout():
    """Logout user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/profile')
@login_required
def profile():
    """Get current user profile"""
    user = current_user
    return jsonify(
        {
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'posts': [{'id': post.id, 'title': post.title} for post in user.posts],
            'user_id': user.id
        }
    )


@app.route('/posts', methods=['POST'])
@login_required
def create_post():
    """Create a new post"""
    title = request.form.get('title')
    content = request.form.get('content')
    
    if not all([title, content]):
        return jsonify({'error': 'Title and content are required'}), 400
    
    # Handle file upload if present
    file_path = None
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add user_id to filename to avoid conflicts
            filename = f"{current_user.id}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
    
    post = Post(title=title, content=content, file_path=file_path, user_id=current_user.id) # type: ignore
    
    db.session.add(post)
    db.session.commit()
    
    return jsonify({
        'message': 'Post created successfully',
        'post': {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'file_path': post.file_path,
            'user_id': post.user_id
        }
    }), 201


@app.route('/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    """Get a specific post with all its comments"""
    post = Post.query.get(post_id)
    
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    
    # Get all comments for this post
    comments = Comment.query.filter_by(post_id=post_id).all()
    
    return jsonify({
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'file_path': post.file_path,
        'user_id': post.user_id,
        'author': {
            'id': post.author.id,
            'username': post.author.username,
            'name': post.author.name
        },
        'comments_count': len(comments),
        'comments': [
            {
                'id': comment.id,
                'text': comment.text,
                'user_id': comment.user_id,
                'commenter': {
                    'id': comment.commenter.id,
                    'username': comment.commenter.username,
                    'name': comment.commenter.name
                }
            } for comment in comments
        ]
    }), 200


@app.route('/posts', methods=['GET'])
def get_all_posts():
    """Get all posts"""
    posts = Post.query.all()
    
    return jsonify({
        'posts': [
            {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'file_path': post.file_path,
                'user_id': post.user_id,
                'author': post.author.username
            } for post in posts
        ]
    }), 200


@app.route('/posts/<int:post_id>/edit', methods=['PUT', 'PATCH'])
@login_required
def edit_post(post_id):
    """Edit/Update a post"""
    post = Post.query.get(post_id)
    
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    
    # Check if the current user is the author
    if post.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized to edit this post'}), 403
    
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        remove_file = data.get('remove_file', False)
        
        if title:
            post.title = title
        if content:
            post.content = content
        
        # Handle file removal
        if remove_file and post.file_path:
            if os.path.exists(post.file_path):
                os.remove(post.file_path)
            post.file_path = None
    else:
        # Handle form data (for file uploads)
        title = request.form.get('title')
        content = request.form.get('content')
        remove_file = request.form.get('remove_file') == 'true'
        
        if title:
            post.title = title
        if content:
            post.content = content
        
        # Handle file removal
        if remove_file and post.file_path:
            if os.path.exists(post.file_path):
                os.remove(post.file_path)
            post.file_path = None
        
        # Handle new file upload
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                # Delete old file if exists
                if post.file_path and os.path.exists(post.file_path):
                    os.remove(post.file_path)
                
                filename = secure_filename(file.filename)
                filename = f"{current_user.id}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                post.file_path = file_path
    
    db.session.commit()
    
    return jsonify({
        'message': 'Post updated successfully',
        'post': {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'file_path': post.file_path,
            'user_id': post.user_id
        }
    }), 200


@app.route('/posts/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    """Delete a post"""
    post = Post.query.get(post_id)
    
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    
    # Check if the current user is the author
    if post.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized to delete this post'}), 403
    
    # Delete associated file if exists
    if post.file_path and os.path.exists(post.file_path):
        os.remove(post.file_path)
    
    # Delete all comments associated with the post
    Comment.query.filter_by(post_id=post_id).delete()
    
    db.session.delete(post)
    db.session.commit()
    
    return jsonify({'message': 'Post deleted successfully'}), 200


@app.route('/posts/<int:post_id>/comments', methods=['POST'])
@login_required
def add_comment(post_id):
    """Add a comment to a post"""
    post = Post.query.get(post_id)
    
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    
    data = request.get_json()
    text = data.get('text') if data else None
    
    if not text:
        return jsonify({'error': 'Comment text is required'}), 400
    
    comment = Comment(text=text, user_id=current_user.id, post_id=post_id) # type: ignore
    
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({
        'message': 'Comment added successfully',
        'comment': {
            'id': comment.id,
            'text': comment.text,
            'user_id': comment.user_id,
            'post_id': comment.post_id
        }
    }), 201