from blueprints.core import bp as core_bp
from blueprints.products import bp as products_bp
from blueprints.images import bp as images_bp
from blueprints.categories import bp as categories_bp
from blueprints.weights import bp as weights_bp
from blueprints.protein_quality import bp as protein_quality_bp
from blueprints.proxy import bp as proxy_bp
from blueprints.backup import bp as backup_bp
from blueprints.settings import bp as settings_bp
from blueprints.stats import bp as stats_bp
from blueprints.translations import bp as translations_bp
from blueprints.off import bp as off_bp


def register_blueprints(app):
    app.register_blueprint(core_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(weights_bp)
    app.register_blueprint(protein_quality_bp)
    app.register_blueprint(proxy_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(translations_bp)
    app.register_blueprint(off_bp)
