from os import environ
from functools import wraps

from flask import Flask, render_template, session, flash, redirect, url_for
from forms import LoginForm, RegisterForm, AddPackageForm

from auth import Authenticator
from packages import PackageHandler
from emails import EmailHandler

app = Flask(__name__)
# A key is needed for some operations. In particular, for wt forms to protect against CSRF
app.secret_key = environ["FLASK_KEY"]

emailHandler = EmailHandler()
authenticator = Authenticator("database/database.db", emailHandler)
packageHandler = PackageHandler("database/database.db", environ["CHROMEDRIVER_NAME"])

@app.route('/')
def hello_world():
	#TODO: change this method to a home page renderer
	return render_template("main_layout_container.html")

# This function can be applied as a decorator to any other function. Basically, it modifies the passed
# function by first checking if the user is logged in. If so, it runs the passes function.
# See here: https://realpython.com/primer-on-python-decorators/
def login_required(func):
	@wraps(func) # This decorator copies over function attributes like __name__, docstring etc. required by flask for some reason
	def wrapper(*args, **kwargs):
		if "userID" in session and session["userID"] > 0:
			return func(*args, **kwargs)
		else:
			flash("You need to log in to do that!", "danger")
			return redirect(url_for("login"))

	# wrapper is the new function that will be put in place of any function that uses this decorator
	return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
	# The form instance will be automatically filled with data if there is data
	form = LoginForm()
	# Validate the form and check that it was submitted with a POST request
	if form.validate_on_submit():

		# Returns valid user ID if successfull. Since user ID's start from 1, the if statment will
		# always evaluate to true if a user ID is returned
		userID = authenticator.verifyLogin(form.email.data, form.password.data)
		if userID:
			# If the login was successfull then we can store the user ID as we will need it later for
			# querying all of the packages for the user. We redirect them to the list of their packages
			session["userID"] = userID
			flash("Login successful!", "success")
			return redirect(url_for("packageList"))
		else:
			flash("Incorrect username or password. Please try again.", "danger")
			# Need to redirect them back to this page so that if they reload it,
			# the form wont be cached and wont resubmit. Then they wont have to click that popup every time
			return redirect(url_for("login"))
	
	return render_template("login.html", form=form)

# When they log out we remove all session data
@app.route("/logout")
@login_required
def logout():
	session["userID"] = 0
	session.clear()
	flash("You have been logged out!", "primary")
	return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
	# The form instance will be automatically filled with data if there is data
	form = RegisterForm()

	# Validate the form and check that it was submitted (POST request). We dont want to make a new
	# user for a get request (not submitted).
	if form.validate_on_submit():
		#print("Validated POST")
		pendingUserID = authenticator.createNewPendingUser(form.email.data, form.password.data)
		if pendingUserID:
			# If the user does not already exist then it was a success and we can redirect them
			# to the next page, which will tell them that they need to verify their email address
			return render_template("verifyYourEmail.html", email=form.email.data, password=form.password.data)
			#return redirect(url_for("verifyEmailAddress", email=form.email.data))
		else:
			flash("That user already exists!", "danger")
			# Need to redirect them back to this page so that if they reload it,
			# the form wont be cached and wont resubmit. Then they wont have to click that popup every time
			return redirect(url_for("register"))

	# If the request was not submitted (or the user already exists) then we can just render the form normally.
	return render_template("register.html", form=form)

@app.route("/packageList", methods=["GET", "POST"])
@login_required
def packageList():
	form = AddPackageForm()
	# If the form was submitted with a POST request then the user is adding a package
	if form.validate_on_submit():
		if packageHandler.createNewPackage(form.trackingCode.data, session["userID"]):
			flash("Package added successfully!", "success")
			form.trackingCode.data = ""
		else:
			flash("You have already added that package!", "warning")
		# Need to redirect them back to this page so that if they reload it,
		# the form wont be cached and wont resubmit. Then they wont have to click that popup every time
		return redirect(url_for("packageList"))

	# If the request is just a get request, then we can just render the list of packages
	packageListDict = packageHandler.getListOfPackages(session["userID"])
	return render_template("packageList.html", form=form, packageList=packageListDict)

@app.route("/packageDetails/<int:packageID>")
@login_required
def viewPackage(packageID):
	packageData = packageHandler.getPackageData(packageID, session["userID"])

	# Make sure that the supplied package id is in the list of packages that this user is tracking
	# thr getPackageData function does this automatically for us
	if not packageData:
		flash("You are not tracking that package. Add it!", "primary")
		return redirect(url_for("packageList"))

	# Pass the data to the template where it will be iterated over and rendered
	return render_template("packageData.html", packageData=packageData)

@app.route("/confirmUserEmail/<string:token>")
def confirmUserEmail(token):
	# Returns false if failed, otherwise returns the ID of the new user
	userID = authenticator.createNewUser(token)
	if not userID:
		flash("This link is either invalid or has expired. Please re-register.", "warning")
		return redirect(url_for("register"))
	# If it was a success then we can log them in
	else:
		# We can store the user ID as we will need it later for querying all of the packages for the user.
		# We then redirect them to the list of their packages
		session["userID"] = userID
		flash("Verification successful! You are now logged in.", "success")
		return redirect(url_for("packageList"))

# Will resend the email for a password reset or email verification.
# The resend type specifies whether it is for a pending user or password reset.
@app.route("/resendEmail/<int:resendType>/<string:email>")
def resendEmail(resendType, email):
	# Email verification
	if resendType == 1:
		if not authenticator.sendEmailVerificationEmail(email):
			flash("Something went wrong and we couldn't resend the email. You may need to re-register.", "danger")
		return render_template("verifyYourEmail.html", email=email)
	# Password reset
	elif resendType == 2:
		pass

if __name__ == "__main__":
	app.run(debug=True, use_reloader=False)