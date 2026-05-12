#!/usr/bin/env python3
from app import create_app

app = create_app()
app.name = 'RAP'

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=5000)
