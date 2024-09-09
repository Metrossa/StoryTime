from app import app

# This is necessary for Vercel serverless deployment
if __name__ == '__main__':
    app.run()