import { Component } from '@angular/core';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faArrowUpFromBracket, faCity, faArrowTrendUp } from '@fortawesome/free-solid-svg-icons';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [FontAwesomeModule, RouterLink],
  templateUrl: './dashboard.html',
})
export class Dashboard {
  faArrowUpFromBracket = faArrowUpFromBracket;
  faCity = faCity;
  faArrowTrendUp = faArrowTrendUp;
}
