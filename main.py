from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegistrationForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os
import unicodedata


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)


##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")



##CREATE TABLE IN DB
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    comment_author = relationship("User", back_populates="comments")

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(1000))
    password = db.Column(db.String (100))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

db.create_all()



def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)



@app.route('/', methods=['GET'], defaults={"page": 1})
@app.route('/<int:page>', methods=['GET'])
def get_all_posts(page):
    Id = 0
    if current_user.is_authenticated:
        Id = current_user.id
    posts = BlogPost.query.all()

    if page:
        page = int(page)
    else:
        page = 1

    pages = BlogPost.query.paginate(page=page, per_page=5)

    return render_template("index.html", all_posts=posts, pages=pages, id=Id, logged_in=current_user.is_authenticated)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        password = generate_password_hash(password=form.password.data,  method='pbkdf2:sha256', salt_length=8)
        if User.query.filter_by(email=form.email.data).first() != None:
            redirect(url_for('login'))
        else:
            new_user = User(
                email=form.email.data,
                name=form.name.data,
                password=password
            )

            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Registered successfully.')
            return redirect(url_for('get_all_posts'))



    return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email_client = form.email.data
        password_cleint = form.password.data
        user = User.query.filter_by(email=email_client).first()
        print(user.id)

        if check_password_hash(pwhash=user.password, password=password_cleint):
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            return redirect(url_for('login'))
            flash('Invalid Credentials')
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have successfully logged yourself out.')
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():
        comment = Comment(
            text=form.comment.data,
            post_id=requested_post.id,
            author_id=current_user.id
        )
        db.session.add(comment)
        db.session.commit()
    return render_template("post.html", post=requested_post,  form=form, logged_in=current_user.is_authenticated)


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


@app.route("/new-post", methods=['GET', 'POST'])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, is_edit=False, logged_in=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))


    return render_template("make-post.html", form=edit_form, is_edit=True, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
