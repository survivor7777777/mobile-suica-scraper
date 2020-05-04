#!/usr/bin/env perl

use strict;
use utf8;
use File::Path;
use WWW::Mechanize;
use Time::HiRes qw(usleep);
use JSON q/decode_json/;
use Getopt::Long qw(:config posix_default no_ignore_case gnu_compat auto_abbrev);
binmode(STDOUT, ":utf8");

my $interval = 500000;  # 0.5 seconds
my $output_dir = "data";
my $help;
my $N;

# subroutines

my $file_counter = 0;

sub save_file {
    my $data = shift;
    my $filename;
    for (;;) {
       $filename = sprintf("%s/%05d.gif", $output_dir, $file_counter++);
       last if (! -f $filename);
    }
    print STDERR "$filename\n";

    open(my $fp, ">", $filename) || die "$filename: $!";
    syswrite($fp, $data);
    close($fp);

    1;
}

# main routine

GetOptions(
    "output|o=s" => \$output_dir,
    "interval|i=s" => \$interval,
    "help|h" => \$help,
);

if ($help || @ARGV != 1 || ($N = $ARGV[0]) == 0) {
    print STDERR "Get Captcha Image Files from the Mobile Suica web page\n";
    print STDERR "Usage: $0 [ --output=dir ] [ --interval=M ] N\n";
    print STDERR "--output=dir  specify the directory to save captcha file\n";
    print STDERR "              default=data\n";
    print STDERR "--interval=M  specify the download interval time in microseconds\n";
    print STDERR "              default=500000 (0.5 seconds)\n";
    print STDERR "--help        show this message\n";
    print STDERR "N             number of images to get.\n";
    exit 1;
}

mkpath($output_dir);

my $cookie_jar = {};
my $mech = WWW::Mechanize->new(
    cookie_jar=>$cookie_jar,
    agent=>"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.75 Safari/537.36",
);
push @{ $mech->requests_redirectable }, 'POST';

for (my $i = 0; $i < $N; $i++) {
    $mech->cookie_jar({});

    my $r1 = $mech->get("https://www.mobilesuica.com/");
    die "index: " . $r1->status_line unless $r1->is_success;

    my $captcha = $mech->find_image(url_abs_regex=>qr/WebCaptchaImage.axd/);
    my $r3 = $mech->get($captcha->url);
    die "captcha: " . $r3->status_line unless $r3->is_success;
    save_file($r3->content);

    usleep($interval);
}

1;

