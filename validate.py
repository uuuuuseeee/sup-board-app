#!/usr/bin/env python3
"""
Validation script for the refactored Flask application.
Run this to verify that all functionality is working correctly.
"""
import sys
from app import create_app
from app.extensions import db

def validate_application():
    """Run comprehensive validation checks."""
    
    print("\n" + "=" * 70)
    print("Flask Application Validation")
    print("=" * 70)
    
    # Create app
    print("\n✓ Creating application...")
    app = create_app()
    
    # Check blueprints
    print("✓ Checking blueprints...")
    blueprints = list(app.blueprints.keys())
    assert 'main' in blueprints, "Main blueprint not registered"
    assert 'auth' in blueprints, "Auth blueprint not registered"
    assert 'boards' in blueprints, "Boards blueprint not registered"
    assert 'practices' in blueprints, "Practices blueprint not registered"
    assert 'admin' in blueprints, "Admin blueprint not registered"
    
    # Check routes
    print("✓ Checking routes...")
    routes = [r.endpoint for r in app.url_map.iter_rules()]
    assert len(routes) >= 36, f"Expected 36+ routes, found {len(routes)}"
    
    # Check database
    print("✓ Checking database...")
    with app.app_context():
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        expected = ['user', 'team', 'board', 'practice', 'attendance']
        for table in expected:
            assert table in tables, f"Table '{table}' not found"
    
    # Check CLI
    print("✓ Checking CLI commands...")
    assert 'promote-admin' in app.cli.commands, "promote-admin CLI command not registered"
    
    # Test template rendering
    print("✓ Testing template rendering...")
    app.config['TESTING'] = True
    with app.test_client() as client:
        resp = client.get('/login')
        assert resp.status_code == 200, "Login page not accessible"
    
    print("\n" + "=" * 70)
    print("✓ All validation checks passed!")
    print("=" * 70)
    print("\nThe Flask application is working correctly.")
    print("Start the server with: flask --app wsgi run")
    print("=" * 70 + "\n")
    
    return True

if __name__ == '__main__':
    try:
        success = validate_application()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n✗ Validation failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n")
        sys.exit(1)
