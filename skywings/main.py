from app import app
app.jinja_env.globals.update(divmod=divmod)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)