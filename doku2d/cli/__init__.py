import argparse
import sys


def main():
    
	parser = argparse.ArgumentParser(description="Doku2D Framework")
	subparser = parser.add_subparsers(dest="command", required=True, help="Komutlar")
 
	create = subparser.add_parser("create", help="Doku2D projesi oluşturur.")
	create.add_argument("proje_adi", type=str, help="Oluşturulacak projenin/dizinin adı.")
	
	subparser.add_parser("build", help="Doku2D projesini derler ve çalıştırılabilir proje üretir.")
 
	args = parser.parse_args()
 
	if len(sys.argv) == 1:
    	parser.print_help()
    	sys.exit()
 
	if args.command == "build":
		build()

	if args.command == "create":
		create_project()
     
	


def create_project():
    print("Proje oluşturuluyor.")

def build():
    print("Derleme işlemi başladı")
    
    
main()