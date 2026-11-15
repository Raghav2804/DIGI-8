"""CareerPulse Flask application."""
from flask import Flask, jsonify, render_template, request, flash, redirect, url_for
from config import SECRET_KEY, MAX_CONTENT_LENGTH, APP_VERSION
from database.db import initialize
from routes.pages import pages
from routes.api import api
from services.data_loader import load_bundled_dataset

def create_app():
    app=Flask(__name__)
    app.config.update(SECRET_KEY=SECRET_KEY, MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH, APP_VERSION=APP_VERSION)
    initialize()
    load_bundled_dataset()
    app.register_blueprint(pages); app.register_blueprint(api)
    @app.errorhandler(413)
    def too_large(_):
        if request.path == url_for("pages.settings") and request.method == "POST":
            flash("File is larger than the 64 MB upload limit. Compress or split it, then retry.", "error")
            return redirect(url_for("pages.settings"))
        return jsonify(error="File exceeds the 64 MB upload limit."),413
    @app.errorhandler(404)
    def not_found(_): return render_template("error.html", code=404, message="That page could not be found."),404
    @app.errorhandler(500)
    def server_error(_): return render_template("error.html", code=500, message="Something went wrong. Please retry."),500
    return app

app=create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
