from flask import Flask
from config import config
from .routes.main import main_bp
from .routes.analysis_pr import pr_bp
from .routes.analysis_file import file_bp
from .routes.analysis_code import code_bp
from .routes.analysis_model import model_bp

def create_app(config_name='default'):

    app = Flask(__name__)
    
    app.config.from_object(config[config_name])
    
    app.register_blueprint(main_bp)
    app.register_blueprint(pr_bp, url_prefix='/analysisPR')
    app.register_blueprint(file_bp, url_prefix='/analysisFile')
    app.register_blueprint(code_bp, url_prefix='/analysisCode')
    app.register_blueprint(model_bp, url_prefix='/analysisModel')
    
    return app