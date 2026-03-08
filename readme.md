Architektura bedzie taka 

Scrapy w osobnym kontenerze, 
Scrapy bedzie publikowal do rabbitMQ

RabbitMQ bedzie robil za middleware , odpowiedzialny za przesylanie wiadomosci miedzy serwisami , konkretne kolejki do ustalenia 

Processor w osobnym kontenerze - to bedzie serwis do przetwarzania roznych wiadomosci wchodzacych na middleware 

Processor bedzie odpowiedzialny za zapisywanie danych ostatecznie do BD postgis 
na razie prosty skrypt pythonowy, docelowo w celery jako procesor do rabbitmq 

PostGIS bedzie baza danych na osobnym kontenerze, zawiera wszystkie dane aplikacji , wszystko w jednej bazie danych , nie chce mi sie juz cudowac 

Aplikacja webowa - backend - osobny kontener , bedzie serwowal zapytania wysylane przez frontend , ostatecznie jednak flask zeby wszystko bylo w pythonie , calosc bedzie smigala na kontenerze z unicornem 

Frontend angular - prezentacja danych 

i dojdzie do tego serwer www jak nginx jako kolejny kontener 

czyli mamy 

scraper (scrapy ) -> middleware (rabbitmq) -> ETL (celery) -> DB (postgis) -> backend (flask-unicorn) -> frontend angular +leaflet 
