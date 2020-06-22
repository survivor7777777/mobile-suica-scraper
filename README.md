# mobile-suica-scraper

[日本語の説明](./README-JP.md)もあります

A set of scripts that automatically collect data from the Mobile Suica web page
https://www.mobilesuica.com/.

## What does this software do?

Mobile Suica is very popular electric money in Japan.
If you have one, you would probably like to get the detailed statement digitally.
However, JR's Mobile Suica page is protected by (a little bit old-fashioned) Captcha like

![Mobile Suica Captcha Image](https://github.com/survivor7777777/mobile-suica-scraper/blob/master/sample-Captcha.gif?raw=true)

to prevent a robot from accessing the data.

This set of scripts will solve the Captcha and collect your Mobile Suica usage data from the web pages.

## What do you have to do to use this software?

You have to go through the following steps just once.
1. Get Captcha images as training data
1. Annotate the Captcha images (automatically by using a prebuild CNN model, or manually by a GUI tool)
1. Build a CNN model from the preprocessed training data.

Then, you can (repeatedly) run a script (robot) that automatically logs in to the Mobile Suica web application and collects your data from the application.

![The process flow](https://github.com/survivor7777777/mobile-suica-scraper/blob/master/process-flow.png?raw=true)

## Files

* getcaptcha.pl: Perl script that downloads captcha image files from the Mobile Suica web page.
* prebuild-model/: Directory that contains a pre-build captcha solving model
* auto-annotate.py: Python script that automatically annotates the downloaded captcha images
* annotate.py: Python script that allows you to manually annotate the captcha immages
* ssd.py, extractor,py, multibox\*.py: Chainer CNN model
* train.py: Python script that builds a captcha solving CNN model from the annotated training data
* scrape.pl: Perl script that extracts Mobile Suica data from the Web Page by using the captcha solving CNN
* scrape-mysql.pl: Scrape data from the Web like scrape.pl, store the data in MySQL
* solve.py: Python script that is called by scrape.pl to solve a Captcha

## NO WARRANTY

ABSOLUTELY NO WARRANTY.
THIS SOFTWARE IS FOR EDUCATIONAL PURPOSES ONLY.
USE IT AT YOUR OWN RISK.

## Prerequisites

This software depends on the following libraries and tools:

* Python 3
  * chainer
  * chainercv
  * numpy
  * scipy
  * opencv-python
  * matplotlib
  * Pillow
* Perl
  * WWW::Mechanize
  * Web::Scraper
  * Time::HiRes
  * JSON
  * Getopt::Long
  * DBI

## How to install Python related libraries

Simply use `pip`

    pip install chainer chainercv numpy scipy opencv-python matplotlib Pillow

## How to install Perl related libraries

Simply use `cpan`

    cpan WWW::Mechanize Web::Scraper Time::HiRes JSON Getopt::Long DBI

## How To Build a CNN model for solving captcha

If you don't like to build your own model, you can skip this chapter and proceed to the next chapter **Get data from Mobile Suica web page** by simply running the following command:

    ln -s prebuild-model model

### Download captcha images from the web

Run `getcaptcha.pl` script as follows:

    ./getcaptcha.pl --interval=500000 100

In this case, this script downloads 100 images from the web at 500ms intervals in `./data` directory.  Do not specify a small interval, since the script may be considered a DOS attack.

### Automatically or manually annotate the downloaded images

Run `auto-annotate.py` script to automatically annotate the downloaded images as follows:

    ./auto-annotate.py

Then, the script generates `./data/dataset.json` file that contains the automatically generated annotation.

The prebuild model is not 100% accurate.  The auto-generated annotation may contain about 10% errors.
Thus you should also review and revise the annotation by using `annotate.py` script as follows:

    ./annotate.py

Then, a window panel will open.  You can interactively edit the automatically generated annotation. 

### Build a captcha solving CNN model from the segmented images

Run `train.py` script to build a captcha solving CNN model in `model` directory

    ./train.py

This may take some time (depending on your machine power -- can be a few hundred seconds or a few hours).
If your machine has NVIDIA GPU and you have CUDA library installed, add --gpu=0 option to make use of the GPU.

You will have a trained model in `./model` directory.

## Get data from Mobile Suica web page

### Create a file containing mobile suica credentials

Create a file `./credentials.json` with the following content:

    {
      "user": "YOUR Mobile SUICA Account (E-Mail address)",
      "password": "YOUR Mobile SUICA Password"
    }

Since it contains your password, you should set it's permission appropriately like the following

    chmod 600 ./credentials.json

Up to here, you have to do just once.

### Get data from Mobile Suica web page in CSV format

To get mobile suica data from https://www.mobilesuica.com/, run `./scrape.pl` script as follows:

    ./scrape.pl

Then, you will see the list of your mobile suica usage in the standard output.  In `./data` directory, newly downloaded captcha files will be stored. You can make use of them for the additional training of the model.  In `./log` directory you can find log information.

### Get data from Mobile Suica web page in a database

If you want to store the scraped data in a database, prepare a file named `./dbi-config.json` with the following content:

	{
	"driver": "DBI driver name (ex. DBI:mysql, DBI:SQLite",
	"database": "database name",
	"user": "database user name",
	"password": "database password",
	"table": "table name (ex. expense)",
	"options": { "RaiseError": 1, "PrintError": 0, "AutoCommit": 0 }
	}

This file also contains your password, so you should set it's permission appropriately with `chmod 600 ./dbi-config.json`.

You have to create a database table with the following SQL statements. (Here, we assumed the database table is named `expense`.)

	create table expense (
	id int not null auto_increment,
	date date,
	type1 varchar(16),
	loc1 varchar(16),
	type2 varchar(16),
	loc2 varchar(16),
	balance int,
	delta int
	remarks varchar(256),
	primary key(id)
	);

	create index expense_date on expense(date);

Then executing　`./scrape.pl --db` will scrape the data and store them in the database table specified.

Enjoy!

## How does this software work?

TBD.
