from app import create_app

app = create_app()

if __name__ == "__main__":
    print(f"ProGuide is running at http://127.0.0.1:5000")
    print(f"Default admin username: admin")
    app.run(host="127.0.0.1", port=5000, debug=False)
