from flask import Blueprint, jsonify

test_bp = Blueprint('test', __name__)

@test_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Multi-tenant FUB API system is running",
        "version": "1.0.0"
    })

@test_bp.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint"""
    return jsonify({"message": "pong"}) 