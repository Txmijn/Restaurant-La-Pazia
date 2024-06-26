from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3

class DatabaseManager:
    DATABASE_URI = "database.sqlite"
    
    @staticmethod
    def get_connection():
        return sqlite3.connect(DatabaseManager.DATABASE_URI)

class MyApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.configure_app()
        self.add_routes()

    def run(self):
        self.app.run(debug=True)

    def configure_app(self):
        self.app.secret_key = 'wat_een_geheime_sleutel'

    def add_routes(self):
        @self.app.route('/')
        def home():
            return render_template('home/index.html')

        @self.app.route('/reserveren')
        def reserveren():
            today = datetime.today().strftime('%Y-%m-%d')
            max_date = (datetime.today() + timedelta(days=14)).strftime('%Y-%m-%d')
            return render_template('reserveren/reserveren.html', today=today, max_date=max_date)
        
        @self.app.route('/reserveren-success')
        def reserveren_success():
            return render_template("reserveren/reserveren-success.html")
        
        @self.app.route('/menu')
        def menu():
            return render_template('menu/menu.html')

        @self.app.route('/overons')
        def overons():
            return render_template('overons/overons.html')

        @self.app.route('/contact')
        def contact():
            return render_template('contact/contact.html')
        
        @self.app.route('/register', methods=['GET', 'POST'])
        def register():
            if not (session.get('logged_in') and session.get('is_admin')):
                flash('U heeft niet de benodigde rechten om deze pagina te kunnen bekijken.')
                return redirect(url_for('login'))

            if request.method == 'POST':
                username = request.form['username']
                password = request.form['password']
                is_admin = request.form.get('is_admin') == 'on'
            
                if len(username) < 5:
                    flash('Gebruikersnaam moet minstens 5 karakters lang zijn.')
                    return redirect(url_for('register'))

                if len(password) < 8:
                    flash('Wachtwoord moet minstens 8 karakters lang zijn.')
                    return redirect(url_for('register'))
        
                if not any(char.isdigit() for char in password):
                    flash('Wachtwoord moet minstens één cijfer bevatten.')
                    return redirect(url_for('register'))
            
                if not any(char.isalpha() for char in password):
                    flash('Wachtwoord moet minstens één letter bevatten.')
                    return redirect(url_for('register'))

                password_hash = generate_password_hash(password)

                try:
                    with DatabaseManager.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", 
                            (username, password_hash, is_admin))
                        conn.commit()
                        flash('Gebruiker succesvol geregistreerd.', 'success')
                except sqlite3.IntegrityError:
                    flash('Deze gebruikersnaam bestaat al.', 'error')
                return redirect(url_for('register'))
            return render_template('admin/register.html')

        
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('gebruikersnaam')
                password = request.form.get('wachtwoord')
        
                with DatabaseManager.get_connection() as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM users WHERE username=?", (username,))
                    user = cur.fetchone()

                if user and check_password_hash(user['password'], password):
           
                    with DatabaseManager.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.now(), user['id']))
                        conn.commit()

                    session['logged_in'] = True
                    session['username'] = username
                    session['is_admin'] = user['is_admin'] == 1
                    return redirect(url_for('admin'))
                else:
                    flash('Ongeldige gebruikersnaam of wachtwoord.')
                    return redirect(url_for('login'))
            else:
                return render_template('login/login.html')

        @self.app.route('/admin')
        def admin():
            if 'logged_in' in session:
                with sqlite3.connect('database.sqlite') as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()

                    cur.execute("SELECT COUNT(*) FROM reserveringen")
                    totaal_reserveringen = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM contact")
                    totaal_contactberichten = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM users")
                    totaal_gebruikers = cur.fetchone()[0]

                    vandaag = datetime.now().strftime('%Y-%m-%d')
                    cur.execute("SELECT COUNT(*) FROM reserveringen WHERE datum = ?", (vandaag,))
                    reserveringen_vandaag = cur.fetchone()[0]

                    return render_template('admin/admin.html', totaal_reserveringen=totaal_reserveringen, totaal_contactberichten=totaal_contactberichten, totaal_gebruikers=totaal_gebruikers, reserveringen_vandaag=reserveringen_vandaag)
            else:
                return redirect(url_for('login'))
            
        @self.app.route('/toggle_admin/<int:user_id>', methods=['POST'])
        def toggle_admin(user_id):
            if 'logged_in' in session:
                with DatabaseManager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT is_admin FROM users WHERE username = ?", (session['username'],))
                    current_user_admin_status = cur.fetchone()[0]

                    if current_user_admin_status:
                        cur.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
                        is_admin = cur.fetchone()[0]
                        new_status = not is_admin
                        cur.execute("UPDATE users SET is_admin = ? WHERE id = ?", (new_status, user_id))
                        conn.commit()
                        flash('De rechten van de gebruiker zijn succesvol bijgewerkt.')
                        return redirect(url_for('view_users'))
                    else:
                        flash('U heeft niet de benodigde rechten om deze actie uit te voeren.')
                        return redirect(url_for('login'))     
            else:
                flash('U bent niet ingelogd.')
                return redirect(url_for('login'))

        @self.app.route('/delete_user/<int:user_id>', methods=['POST'])
        def delete_user(user_id):
            if 'logged_in' in session:
                with DatabaseManager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT is_admin FROM users WHERE username = ?", (session['username'],))
                    current_user_admin_status = cur.fetchone()[0]

                if current_user_admin_status:
                    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    conn.commit()
                    flash('Gebruiker succesvol verwijderd.')
                    return redirect(url_for('view_users'))
                else:
                    flash('U heeft niet de benodigde rechten om deze actie uit te voeren.')
                    return redirect(url_for('login'))
            else:
                flash('U bent niet ingelogd.')
                return redirect(url_for('login'))

        @self.app.route('/submit-reservation', methods=['POST'])
        def submit_reservation():
            voornaam = request.form['voornaam']
            achternaam = request.form['achternaam']
            email = request.form['email']
            telefoonnummer = request.form['telefoonnummer']
            aantalPersonen = int(request.form['aantalPersonen'])
            datum = request.form['datum']
            reserveringstijd = request.form['reserveringstijd']
            laatste_reserveringstijd = datetime.strptime("21:00", "%H:%M").time()
            ingevoerde_tijd = datetime.strptime(reserveringstijd, "%H:%M").time()

            if voornaam.isdigit() or achternaam.isdigit():
                flash('Error: Gebruik aub alleen letters bij uw voornaam en of achternaam.')
                return redirect(url_for('reserveren'))  
            elif aantalPersonen > 8:
                flash('Error: Meer dan 8 personen reserveren is niet mogelijk. Pas het aantal personen aan.')
                return redirect(url_for('reserveren'))  
            elif not telefoonnummer.isdigit():
                flash('Error: Telefoonnummer is niet geldig. Gebruik alleen cijfers.')
                return redirect(url_for('reserveren'))
            elif ingevoerde_tijd > laatste_reserveringstijd:
                flash('Error: Reserveren na 21:00 is niet toegestaan.')
                
            with DatabaseManager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO reserveringen (voornaam, achternaam, email, telefoonnummer, aantalPersonen, datum, reserveringstijd) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (voornaam, achternaam, email, telefoonnummer, aantalPersonen, datum, reserveringstijd))
                conn.commit()
            return redirect(url_for('reserveren_success'))  

        @self.app.route('/submit-contact', methods=['POST'])
        def submit_contact():
            voornaam = request.form['voornaam']
            achternaam = request.form['achternaam']
            emailadres = request.form['emailadres']
            vraag = request.form['vraag']
            if voornaam.isdigit() or achternaam.isdigit():
                flash('Error: Gebruik aub alleen letters bij uw voornaam en of achternaam.')
                return redirect(url_for('contact'))  
            with DatabaseManager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO contact (voornaam, achternaam, emailadres, vraag) VALUES (?, ?, ?, ?)",
                    (voornaam, achternaam, emailadres, vraag))
                conn.commit()
            return render_template('contact/contact-success.html')  

        @self.app.route('/view_reservations')
        def view_reservations():
            if 'logged_in' in session:
                with sqlite3.connect('database.sqlite') as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE reserveringen SET id = (SELECT COUNT(*) FROM reserveringen r WHERE r.id <= reserveringen.id)")
                    cur.execute("SELECT * FROM reserveringen ORDER BY datum")
                    reservations = cur.fetchall()
                    vandaag = datetime.now()
                    vandaag_str = vandaag.strftime('%Y-%m-%d')
                    cur.execute("SELECT SUM(aantalPersonen) FROM reserveringen WHERE datum = ?", (vandaag_str,))
                    aantal_mensen_vandaag = cur.fetchone()[0] or 0
                    datum_vandaag = vandaag.strftime('%d-%m-%Y')
                    return render_template('admin/view-reserveringen.html', reservations=reservations, aantal_mensen=aantal_mensen_vandaag, datum_vandaag=datum_vandaag)
            else:
                return redirect(url_for('login')) 
             
        @self.app.route('/update_reservation/<int:reservation_id>', methods=['POST'])
        def update_reservation(reservation_id):
            if 'logged_in' in session:
                data = request.json
                voornaam = data['voornaam']
                achternaam = data['achternaam']
                email = data['email']
                telefoonnummer = data['telefoonnummer']
                aantalPersonen = data['aantalPersonen']
                datum = data['datum']
                reserveringstijd = data['reserveringstijd']

                with DatabaseManager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE reserveringen SET voornaam=?, achternaam=?, email=?, telefoonnummer=?, aantalPersonen=?, datum=?, reserveringstijd=? WHERE id=?",
                                (voornaam, achternaam, email, telefoonnummer, aantalPersonen, datum, reserveringstijd, reservation_id))
                    conn.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'success': False}), 401
            
        @self.app.route('/delete_reservation/<int:reservation_id>', methods=['POST'])
        def delete_reservation(reservation_id):
            if 'logged_in' in session:
                if request.method == 'POST':
                    with DatabaseManager.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM reserveringen WHERE id=?", (reservation_id,))
                        conn.commit()
                    return redirect(url_for('view_reservations'))
            else:
                return redirect(url_for('login'))

        @self.app.route('/view_contacts')
        def view_contacts():
            if 'logged_in' in session:
                with DatabaseManager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE contact SET id = (SELECT COUNT(*) FROM contact c WHERE c.id <= contact.id)")
                    cur.execute("SELECT * FROM contact")
                    contacts = cur.fetchall()
                return render_template('admin/view-contacten.html', contacts=contacts)
            else:
                return redirect(url_for('login'))

        @self.app.route('/update_contact/<int:contact_id>', methods=['POST'])
        def update_contact(contact_id):
            if 'logged_in' in session:
                try:
                    data = request.json  
                    voornaam = data['voornaam']
                    achternaam = data['achternaam']
                    email = data['email']
                    vraag = data['vraag']
                    
                    with DatabaseManager.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE contact SET voornaam=?, achternaam=?, emailadres=?, vraag=? WHERE id=?",
                                    (voornaam, achternaam, email, vraag, contact_id))
                        conn.commit()
                    return jsonify({'success': True})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)})
            else:
                return jsonify({'success': False}), 401

        @self.app.route('/delete_contact/<int:contact_id>', methods=['POST'])
        def delete_contact(contact_id):
            if 'logged_in' in session:
                with DatabaseManager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM contact WHERE id=?", (contact_id,))
                    conn.commit()
                return redirect(url_for('view_contacts'))
            else:
                return redirect(url_for('login'))

        @self.app.route('/view_users')
        def view_users():
            if 'logged_in' in session:
                with DatabaseManager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT is_admin FROM users WHERE username = ?", (session['username'],))
                    current_user_admin_status = cur.fetchone()[0]

                if current_user_admin_status:
                    cur.execute("SELECT id, username, password, is_admin, last_login FROM users")
                    users = cur.fetchall()
                    return render_template('admin/view-users.html', users=users)
                else:
                    flash('U heeft niet de benodigde rechten om deze pagina te kunnen bekijken.')
                    return redirect(url_for('admin'))
            else:
                flash('U bent niet ingelogd.')
                return redirect(url_for('login'))

        @self.app.route('/logout')
        def logout():
            session.pop('logged_in', None)
            session.pop('username', None)
            session.pop('is_admin', None)
            return redirect(url_for('home'))
    
if __name__ == '__main__':
    app_instance = MyApp()
    app_instance.run()
