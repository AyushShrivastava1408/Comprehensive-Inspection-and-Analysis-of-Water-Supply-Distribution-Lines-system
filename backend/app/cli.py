import click

from .constants import ROLE_ADMIN
from .extensions import db
from .models import User


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(username, email, password):
        """Pehla admin user banata hai."""
        if User.query.filter((User.username == username) | (User.email == email.lower())).first():
            raise click.ClickException("User already exists")
        u = User(username=username, email=email.lower(), role=ROLE_ADMIN)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.echo(f"Admin '{username}' created.")
