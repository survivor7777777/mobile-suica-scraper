#!/bin/bash
# This script creates a new database and "mysql-config.json" file that scrape-mysql.pl uses.

# change the following parameters as you like
database=expense
user=expense
password=expense
table=expense

# create database
echo Creating a database named [$database] 1>&2
echo ENTER MYSQL ROOT PASSWORD. 1>&2
mysqladmin -u root -p create $database

# create user
echo Creating a user named [$user] 1>&2
echo ENTER MYSQL ROOT PASSWORD, AGAIN. 1>&2
mysql -u root -p $database <<EOS1
grant all privileges on *.* to '$user'@'localhost' identified by '$password';
EOS1

# create table and index
echo Creating a table named [$table] 1>&2
mysql -u $user -p$password $database <<EOS2
CREATE TABLE $table (
  id int NOT NULL AUTO_INCREMENT,
  date date NOT NULL,
  type1 varchar(16) DEFAULT NULL,
  loc1 varchar(16) DEFAULT NULL,
  type2 varchar(16) DEFAULT NULL,
  loc2 varchar(16) DEFAULT NULL,
  balance int DEFAULT NULL,
  delta int DEFAULT NULL,
  remarks varchar(256) DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
CREATE INDEX ${table}_date on $table(date);
EOS2

# create mysql-config.json file
echo Creating mysql-config.json file 1>&2
cat >mysql-config.json <<EOS3
{
"database": "$database",
"user": "$user",
"password": "$password",
"table": "$table"
}
EOS3

# completed!
echo Completed! 1>&2

exit 0
