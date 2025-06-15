
## 🧑‍💻 **MelaScan Setup Guide (Windows)**


### 1. Create & Activate Virtual Environment

```bash
python -m venv venv
.\venv\Scripts\Activate
```

---

### 2 . Install Requirements

```bash
pip install -r requirements.txt
```

---

### 3. Configure Environment

- Make sure `.env` exists in the project folder.
- It should include:
  ```env
  FLASK_APP=app
  FLASK_ENV=development
  SECRET_KEY=your-secret-key
  SQLALCHEMY_DATABASE_URI=sqlite:///mela.db
  UPLOAD_FOLDER=uploads
  ```

---

### 4. Run Database Migrations

```bash
flask db upgrade
```

> First-time setup:
```bash
flask db init
flask db migrate -m "Initial"
flask db upgrade
```

### additional imports
pip install torch
pip install numpy
pip install Pillow
pip install torchvision
pip install fpdf
.env created for uploads
