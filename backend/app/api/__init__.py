def register_blueprints(app):
    from .auth import bp as auth_bp
    from .dashboard import bp as dash_bp
    from .detections import bp as det_bp
    from .images import bp as img_bp
    from .inspections import bp as insp_bp
    from .reports import bp as rep_bp

    for bp in (auth_bp, insp_bp, img_bp, det_bp, dash_bp, rep_bp):
        app.register_blueprint(bp, url_prefix="/api")
