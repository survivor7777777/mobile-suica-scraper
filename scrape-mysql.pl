#!/usr/bin/perl

use strict;
use utf8;
use WWW::Mechanize;
use Web::Scraper;
use JSON;
use File::Path;
use File::Basename;
use Getopt::Long qw(:config posix_default no_ignore_case gnu_compat auto_abbrev);
use DBI;
binmode(STDOUT, ":utf8");
binmode(STDERR, ":utf8");

my $credential_file = "credentials.json";
my $model_file = "model/parameters.json";
my $gpu = -1;
my $output_dir = "log";
my $mysql_config_file = "mysql-config.json";
my $verbose = 0;

GetOptions(
    "credentials|c=s" => \$credential_file,
    "model|m=s" => \$model_file,
    "gpu|g=i" => \$gpu,
    "output|o=s" => \$output_dir,
    "mysql|d=s" => \$mysql_config_file,
    "verbose|v" => \$verbose,
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
	my $file_name = sprintf("%s%d%s", $base, $i, $ext);
	return $file_name unless -e $file_name;
    }
}

# check if output directory exists
if (! -d $output_dir) {
    mkpath($output_dir);
}
my $log_file = "$output_dir/scrape.log";
open(my $log, ">>:utf8", $log_file) || die "$log_file: $!";
print $log "#-------- " . localtime() . " --------\n";

# read mysql-config file
my $mysql_config = decode_json(read_file($mysql_config_file));

# read credential file
if (! -r $credential_file) {
    print STDERR "$credential_file: not found\n" if $verbose;
    print STDERR "You must create a file like the following:\n" if $verbose;
    print STDERR <<EOS if $verbose;
{
  "user": "YOUR SUICA ACCOUNT (Mail-Address)",
  "password": "YOUR SUICA PASSWORD"
}
EOS
    print STDERR "You should set the permission appropriately by executing the following command so that others cannot read it.\n" if $verbose;
    print STDERR "chmod 600 $credential_file\n" if $verbose;
    exit 1;
}
my $credentials = decode_json(read_file($credential_file));

# setup WWW::Mechanize
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
    my $captcha_string = "";
    pipe(my $parent_read, my $child_write);
    pipe(my $child_read, my $parent_write);
    $child_write->autoflush(1);
    $parent_write->autoflush(1);
    my $pid = fork(); die "fork: $!" unless defined($pid);
    if ($pid == 0) { # child process
	close($parent_read);
	close($parent_write);
	open(STDIN, "<&", $child_read);
	open(STDOUT, ">&", $child_write);
	exec("./solve.py --model=$model_file --gpu=$gpu");
    }
    else { # parent process
	close($child_read);
	close($child_write);
	syswrite($parent_write, $captcha_image);
	close($parent_write);
	chop($captcha_string = <$parent_read>);
	close($parent_read);
    }
    my $gif_file = new_file("$output_dir/captcha-", ".gif");
    save_file($gif_file, $captcha_image);

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
	print STDERR "login successful.\n" if $verbose;
	print $log "\"$gif_file\",\"$captcha_string\",1\n";
	last;
    }
    print STDERR "login failed.\n" if $verbose;
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

# database connection
my $dbh = DBI->connect("DBI:mysql:" . $mysql_config->{database},
		       $mysql_config->{user},
		       $mysql_config->{password},
		       { RaiseError=> 1, AutoCommit=>0, mysql_enable_utf8=>1 });
my $stmt1 = $dbh->prepare("select max(date) from " . $mysql_config->{table});
$stmt1->execute();
my $maxdate = eval {
    ($stmt1->fetchrow_array)[0];
} || "1900-01-01";
$stmt1->finish;

my $year = (localtime)[5] + 1900;
my $month = (localtime)[4] + 1;

my @stack;
my $result = $scraper->scrape($r4->decoded_content);
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
    last if $list[0] le $maxdate;
    next if $list[1] eq "繰";

    $list[5] =~ s/[¥,]//g;
    $list[6] =~ s/[¥,]//g;

    print $log "\"" . join("\",\"", @list) . "\"\n";
    unshift @stack, [@list];
}

my $stmt2 = $dbh->prepare("insert into " . $mysql_config->{table} . "(date,type1,loc1,type2,loc2,balance,delta) values(?,?,?,?,?,?,?)");
for my $list (@stack) {
    $stmt2->execute(@$list);
}
$stmt2->finish;
$dbh->commit;
$dbh->disconnect;

close($log);

1;
__END__
