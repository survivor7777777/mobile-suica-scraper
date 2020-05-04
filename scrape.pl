#!/usr/bin/env perl

use strict;
use utf8;
use WWW::Mechanize;
use Web::Scraper;
use JSON;
use File::Path;
use File::Basename;
use DBI;
use Getopt::Long qw(:config posix_default no_ignore_case gnu_compat auto_abbrev);
binmode(STDOUT, ":utf8");
binmode(STDERR, ":utf8");

my $credential_file = "credentials.json";
my $model_dir = "model";
my $gpu = -1;
my $log_dir = "log";
my $data_dir = "data";
my $use_db;
my $dbi_config_file = "dbi-config.json";

GetOptions(
    "credentials|c=s" => \$credential_file,
    "model|m=s" => \$model_dir,
    "gpu|g=i" => \$gpu,
    "data|d=s" => \$data_dir,
    "db" => \$use_db,
);

my $home_dir = dirname($0);
chdir($home_dir);

# subroutines
sub read_file {
    my $file = shift;

    open(my $fp, "<", $file) || die "$file: $!";
    my $buffer;
    while (<$fp>) {
	$buffer .= $_;
    }
    close($fp);

    return $buffer;
}

sub save_file {
    my $file = shift;
    my $content = shift;

    open(my $fp, ">", $file) || die "$file: $!";
    print $fp $content;
    close($fp);

    return 1;
}

sub new_file {
    my $base = shift;
    my $ext = shift;
    for (my $i = 0; ; $i++) {
	my $file_name = sprintf("%s%05d%s", $base, $i, $ext);
	return $file_name unless -e $file_name;
    }
}

# check if data and log directories exist
mkpath($data_dir) unless -d $data_dir;
mkpath($log_dir) unless -d $log_dir;

my $log_file = "$log_dir/scrape.log";
open(my $log, ">>:utf8", $log_file) || die "$log_file: $!";
print $log "#-------- " . localtime() . " --------\n";

# read credential file
if (! -r $credential_file) {
    print STDERR "$credential_file: not found\n";
    print STDERR "You must create a file named 'credential_file' with the following content:\n";
    print STDERR <<EOS;
{
  "user": "YOUR Mobile SUICA Account (E-Mail address)",
  "password": "YOUR Mobile SUICA Password"
}
EOS
    print STDERR "You should set the permission appropriately by executing the following command so that others cannot read it.\n";
    print STDERR "chmod 600 $credential_file\n";
    exit 1;
}
my $credentials = decode_json(read_file($credential_file));

# read dbi-config if needed
my $dbi_config;
if ($use_db) {
    $dbi_config = decode_json(read_file($dbi_config_file));
}

# initialize WWW::Mechanize
my $cookie_jar = {};
my $mech = WWW::Mechanize->new(
    cookie_jar => $cookie_jar,
    agent => "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.75 Safari/537.36",
);
push @{ $mech->requests_redirectable }, 'POST';

my $url = [
"https://www.mobilesuica.com/",
"https://www.mobilesuica.com/iq/ir/SuicaDisp.aspx?returnId=SFRCMMEPC03",
    ];

# output package

package output_csv;

sub new {
    my $class = shift;
    return bless {}, $class;
}

sub write {
    my $self = shift;
    my @list = @_;
    print "\"" . join("\",\"", @list) . "\"\n";    
}

sub close {
    my $self = shift;
    # do nothing
}

package output_db;

sub new {
    my $class = shift;
    
    my $dbh = DBI->connect($dbi_config->{'driver'} . ":" . $dbi_config->{'database'},
			   $dbi_config->{'user'}, $dbi_config->{'password'},
			   $dbi_config->{'options'});

    eval {
	my $sql = <<EOS;
create table $dbi_config->{'table'}(
id int auto_increment primary key,
date date,
type1 varchar(16),
loc1 varchar(16),
type2 varchar(16),
loc2 varchar(16),
balance int,
delta int,
remarks varchar(256)
)
EOS
	$dbh->do($sql);
	$dbh->do("create index " . $dbi_config->{'table'} . "_date on " . $dbi_config->{'table'} . "(date)");
    };

    my $stmt0 = $dbh->prepare("select max(date) from " . $dbi_config->{'table'});
    $stmt0->execute();
    my $maxdate = eval {
	($stmt0->fetchrow_array)[0];
    } || "1900-01-01";
    $stmt0->finish;

    my $stmt = $dbh->prepare("insert into " . $dbi_config->{'table'} . "(date,type1,loc1,type2,loc2,balance,delta) values(?,?,?,?,?,?,?)");

    return bless { dbh => $dbh, stmt => $stmt, maxdate => $maxdate }, $class;
}

sub write {
    my $self = shift;
    my @list = @_;

    return if $list[0] le $self->{'maxdate'};
    $self->{'stmt'}->execute(@list);
}

sub close {
    my $self = shift;
    $self->{'stmt'}->finish;
    $self->{'dbh'}->commit;
    $self->{'dbh'}->disconnect;
}

package main;

# login loop
my $login_success = 0;
for (my $retry = 0; $retry < 3; $retry++) {

    # fetch LOGIN page
    my $r0 = $mech->get($url->[0]);
    die "page0: " . $r0->status_line unless $r0->is_success;

    # check if service time is over
    die "$url->[0] is out of service now" if $mech->uri->as_string =~ /ServiceOvertime.html/;

    # fetch CAPTCHA image
    my $img_tag = $mech->find_image(url_abs_regex=>qr/WebCaptchaImage.axd/);
    die "cannot find img tag" unless $img_tag;
    my $r1 = $mech->get($img_tag->url);
    die "captcha img: " . $r1->status_line unless $r1->is_success;
    my $captcha_image = $r1->content;
    $mech->back() || die "could not go back";

    # solve the captcha
    my $gif_file = new_file("$data_dir/", ".gif");
    save_file($gif_file, $captcha_image);

    my $captcha_string = "";
    open(my $pipe, "-|", "./solve.py --model=$model_dir --file $gif_file") || die "./solve.py: $!";
    chomp(my $result = <$pipe>);
    if ($result =~ /^.*\.gif (.*)$/) {
	$captcha_string = $1;
    }
    next unless length($captcha_string) == 5;

    # fill values in form1
    $mech->form_id("form1");
    $mech->field("MailAddress", $credentials->{user});
    $mech->field("Password", $credentials->{password});
    $mech->field("WebCaptcha1__editor", $captcha_string);
    $mech->field("WebCaptcha1_clientState", "[[[[null]],[],[]],[{},[]],null]");
    my $client_state = sprintf("|0|01%s||[[[[]],[],[]],[{},[]],\"01%s\"]", $captcha_string, $captcha_string);
    $mech->field("WebCaptcha1__editor_clientState", $client_state);
    my $r2 = $mech->click("LOGIN", 100, 10);
    die "page2: " . $r2->status_line unless $r2->is_success;

    # check if login successful
    if ($r2->decoded_content =~ /<title>.*Suica一覧<\/title>/) {
	$login_success = 1;
	print $log "\"$gif_file\",\"$captcha_string\",1\n";
	last;
    }
    print $log "\"$gif_file\",\"$captcha_string\",0\n";
} # end of login loop
die "login unsuccessful" unless $login_success;
# login successful

# choose the first suica
$mech->form_name("form1");
my $r3 = $mech->click("NEXT", 50, 10);
die "select fitst suica: " . $r3->status_line unless $r3->is_success;
die "unknown page transition" unless $mech->uri->as_string =~ /SuicaList.aspx/;

# display page
my $r4 = $mech->post($url->[1]);
die "page4: " . $r4->status_line unless $r4->is_success;

# check if the service time is over
die "$url->[1] is out of service now" if $r4->decoded_content =~ /時間をお確かめの上、再度実行してください。/;

# scraping the data from HTML
my $scraper = scraper {
    process 'table tr td.grybg01 table tr', 'tr[]' => scraper {
	process 'td', 'td[]' => { 'text' => 'TEXT' }
    }
};

my $year = (localtime)[5] + 1900;
my $month = (localtime)[4] + 1;
my $result = $scraper->scrape($r4->decoded_content);
my $output = $use_db ? new output_db() : new output_csv();

for my $row (@{$result->{tr}}) {
    next unless $row->{td};
    next unless scalar(@{$row->{td}}) == 7;
    next unless $row->{td}->[0]->{text} =~ /^(\d*)\/(\d*)$/;

    my $new_month = $1;
    my $day = $2;
    $year-- if $month < $new_month;
    $month = $new_month;

    my @list;
    for my $col (@{$row->{td}}) {
	push @list, $col->{text};
    }
    $list[0] = "$year-$month-$day";
    next if $list[1] eq "繰";

    $list[5] =~ s/[¥,]//g;
    $list[6] =~ s/[¥,]//g;

    $output->write(@list);
}

$output->close();
close($log);

1;
__END__
