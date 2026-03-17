from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import re
import base64
from werkzeug.utils import secure_filename
import PyPDF2
import docx2txt

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(filepath):
    text = ""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"PDF error: {e}")
    return text


def extract_text_from_docx(filepath):
    try:
        return docx2txt.process(filepath)
    except Exception as e:
        print(f"DOCX error: {e}")
        return ""


def extract_text_from_txt(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"TXT error: {e}")
        return ""


def extract_text(filepath):
    ext = filepath.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return extract_text_from_pdf(filepath)
    elif ext in ['doc', 'docx']:
        return extract_text_from_docx(filepath)
    elif ext == 'txt':
        return extract_text_from_txt(filepath)
    return ""


def extract_contact_info(text):
    email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    email = emails[0] if emails else None

    linkedin_pattern = r'(?:linkedin\.com/in/|linkedin\.com/profile/)[a-zA-Z0-9\-_%]+'
    linkedins = re.findall(linkedin_pattern, text.lower())
    linkedin = linkedins[0] if linkedins else None
    if linkedin:
        linkedin = 'https://www.' + linkedin

    return {'email': email, 'linkedin': linkedin}


def extract_strengths(text, matched_skills, job_title):
    strengths = []
    text_lower = text.lower()

    exp_numbers = re.findall(r'\b(\d+)\s*(?:\+\s*)?years?\b', text_lower)
    if exp_numbers:
        max_exp = max(int(x) for x in exp_numbers)
        if max_exp >= 1:
            strengths.append(f"{max_exp}+ years of experience")

    if any(w in text_lower for w in ['ph.d', 'phd', 'doctorate']):
        strengths.append("PhD / Doctorate degree")
    elif any(w in text_lower for w in ['master', 'm.tech', 'm.e.', 'mba', 'msc', 'm.sc']):
        strengths.append("Master's degree")
    elif any(w in text_lower for w in ['bachelor', 'b.tech', 'b.e.', 'bsc', 'b.sc', 'b.com', 'bca', 'bba']):
        strengths.append("Bachelor's degree")

    if any(w in text_lower for w in ['led', 'managed team', 'team lead', 'head of', 'director']):
        strengths.append("Leadership experience")

    if len(matched_skills) >= 3:
        strengths.append(f"Strong skill match ({len(matched_skills)} skills)")
    elif len(matched_skills) > 0:
        strengths.append(f"Partial skill match ({len(matched_skills)} skills)")

    if any(w in text_lower for w in ['certified', 'certification', 'certificate']):
        strengths.append("Holds certifications")

    if any(w in text_lower for w in ['project', 'developed', 'built', 'designed', 'implemented']):
        strengths.append("Hands-on project experience")

    if any(w in text_lower for w in ['published', 'research paper', 'journal', 'conference']):
        strengths.append("Research / publications")

    return strengths[:4]


def get_file_preview(filepath):
    ext = filepath.rsplit('.', 1)[1].lower()
    try:
        if ext == 'pdf':
            with open(filepath, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            return {'type': 'pdf', 'data': encoded}
        elif ext in ['doc', 'docx']:
            text = extract_text_from_docx(filepath)
            return {'type': 'text', 'data': text[:3000]}
        elif ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            return {'type': 'text', 'data': text[:3000]}
    except Exception as e:
        print(f"Preview error: {e}")
    return {'type': 'none', 'data': ''}


def calculate_score(resume_text, job_title, job_desc, required_skills, experience):
    text_lower = resume_text.lower()
    score = 0
    matched_skills = []
    missing_skills = []

    if required_skills:
        for skill in required_skills:
            if skill.lower() in text_lower:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)
        score += (len(matched_skills) / len(required_skills)) * 50

    title_words = job_title.lower().split()
    title_hits = sum(1 for w in title_words if w in text_lower)
    score += (title_hits / max(len(title_words), 1)) * 20

    desc_words = [w for w in re.findall(r'\b\w{4,}\b', job_desc.lower())
                  if w not in {'with', 'that', 'this', 'have', 'from', 'will', 'your', 'they', 'been', 'more'}]
    desc_words = list(set(desc_words))
    if desc_words:
        desc_hits = sum(1 for w in desc_words if w in text_lower)
        score += (desc_hits / len(desc_words)) * 20

    exp_score = 0
    if experience:
        exp_numbers = re.findall(r'\b(\d+)\s*(?:\+\s*)?years?\b', text_lower)
        if exp_numbers:
            candidate_exp = max(int(x) for x in exp_numbers)
            if '0-1' in experience or '0–1' in experience or 'fresher' in experience.lower():
                exp_score = 10 if candidate_exp <= 1 else 5
            elif '1-3' in experience or '1–3' in experience:
                exp_score = 10 if 1 <= candidate_exp <= 3 else 6
            elif '3-5' in experience or '3–5' in experience:
                exp_score = 10 if 3 <= candidate_exp <= 5 else 6
            elif '5-8' in experience or '5–8' in experience:
                exp_score = 10 if 5 <= candidate_exp <= 8 else 6
            elif '8+' in experience:
                exp_score = 10 if candidate_exp >= 8 else 5
    score += exp_score

    if not required_skills:
        score = (title_hits / max(len(title_words), 1)) * 50
        if desc_words:
            desc_hits = sum(1 for w in desc_words if w in text_lower)
            score += (desc_hits / len(desc_words)) * 40
        score += exp_score

    return round(min(score, 100)), matched_skills, missing_skills


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/screen', methods=['POST'])
def screen_resumes():
    job_title = request.form.get('jobTitle', '').strip()
    job_desc = request.form.get('jobDesc', '').strip()
    department = request.form.get('department', '').strip()
    experience = request.form.get('experience', '').strip()
    top_n = int(request.form.get('topN', 10))
    skills_raw = request.form.get('skills', '')
    required_skills = [s.strip() for s in skills_raw.split(',') if s.strip()]

    if not job_title or not job_desc:
        return jsonify({'error': 'Job title and description are required.'}), 400

    files = request.files.getlist('resumes')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No resumes uploaded.'}), 400

    results = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            resume_text = extract_text(filepath)
            score, matched, missing = calculate_score(resume_text, job_title, job_desc, required_skills, experience)
            contact = extract_contact_info(resume_text)
            strengths = extract_strengths(resume_text, matched, job_title)
            preview = get_file_preview(filepath)

            results.append({
                'filename': filename,
                'score': score,
                'matched_skills': matched,
                'missing_skills': missing,
                'contact': contact,
                'strengths': strengths,
                'preview': preview
            })

            try:
                os.remove(filepath)
            except:
                pass

    if not results:
        return jsonify({'error': 'No valid resume files found.'}), 400

    results.sort(key=lambda x: x['score'], reverse=True)
    top_results = results[:top_n]
    for i, r in enumerate(top_results):
        r['rank'] = i + 1

    return jsonify({
        'success': True,
        'total_uploaded': len(results),
        'top_n': top_n,
        'job_title': job_title,
        'required_skills': required_skills,
        'results': top_results
    })


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  ResumeRank Server Starting...")
    print(f"  Open your browser: http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port)
