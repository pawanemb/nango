"""
Country Code Conversion Service

This service converts ISO 3166-1 alpha-2 country codes (2-letter format) 
to full country names for use in AI prompts and title generation.

Supports SEMrush-style country codes:
- US -> United States
- IN -> India  
- GB -> United Kingdom
- DE -> Germany
- AE -> United Arab Emirates
"""

import pycountry
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class CountryService:
    """Service for converting country codes to full country names."""
    
    # Custom mappings for special cases or preferred names
    CUSTOM_COUNTRY_MAPPINGS = {
        "US": "United States",
        "GB": "United Kingdom", 
        "AE": "United Arab Emirates",
        "KR": "South Korea",
        "TW": "Taiwan",
        "VN": "Vietnam",
        "RU": "Russia",
        "IR": "Iran",
        "SY": "Syria",
        "VE": "Venezuela",
        "BO": "Bolivia",
        "TZ": "Tanzania",
        "CD": "Democratic Republic of the Congo",
        "CG": "Republic of the Congo",
        "MK": "North Macedonia",
        "MD": "Moldova",
        "PS": "Palestine"
    }
    
    @classmethod
    def get_country_name(cls, country_code: str) -> str:
        """
        Convert ISO 3166-1 alpha-2 country code to full country name.
        
        Args:
            country_code: 2-letter country code (e.g., "US", "IN", "GB")
            
        Returns:
            Full country name (e.g., "United States", "India", "United Kingdom")
            
        Raises:
            ValueError: If country code is invalid or not found
        """
        if not country_code:
            raise ValueError("Country code cannot be empty")
            
        # Convert to uppercase for consistency
        country_code = country_code.upper().strip()
        
        # Validate format (should be exactly 2 letters)
        if len(country_code) != 2 or not country_code.isalpha():
            raise ValueError(f"Invalid country code format: {country_code}. Must be 2 letters (ISO 3166-1 alpha-2)")
        
        # Check custom mappings first
        if country_code in cls.CUSTOM_COUNTRY_MAPPINGS:
            country_name = cls.CUSTOM_COUNTRY_MAPPINGS[country_code]
            logger.info(f"Country code '{country_code}' converted to '{country_name}' (custom mapping)")
            return country_name
        
        # Use pycountry for standard lookup
        try:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                country_name = country.name
                logger.info(f"Country code '{country_code}' converted to '{country_name}' (pycountry)")
                return country_name
            else:
                raise ValueError(f"Country code '{country_code}' not found in ISO 3166-1 database")
                
        except Exception as e:
            logger.error(f"Error converting country code '{country_code}': {str(e)}")
            raise ValueError(f"Failed to convert country code '{country_code}': {str(e)}")
    
    @classmethod
    def is_valid_country_code(cls, country_code: str) -> bool:
        """
        Check if a country code is valid ISO 3166-1 alpha-2 format.
        
        Args:
            country_code: 2-letter country code to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            cls.get_country_name(country_code)
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_supported_countries(cls) -> dict:
        """
        Get all supported country codes and their names.
        
        Returns:
            Dictionary mapping country codes to country names
        """
        supported_countries = {}
        
        # Add custom mappings
        supported_countries.update(cls.CUSTOM_COUNTRY_MAPPINGS)
        
        # Add all pycountry countries
        for country in pycountry.countries:
            if hasattr(country, 'alpha_2') and country.alpha_2:
                # Don't override custom mappings
                if country.alpha_2 not in supported_countries:
                    supported_countries[country.alpha_2] = country.name
        
        return supported_countries
    
    @classmethod
    def get_semrush_common_countries(cls) -> dict:
        """
        Get commonly used countries in SEMrush with their codes and names.
        
        Returns:
            Dictionary of common SEMrush country codes and names
        """
        common_countries = {
            # North America
            "US": "United States",
            "CA": "Canada",
            "MX": "Mexico",
            "GT": "Guatemala",
            "CR": "Costa Rica",
            "PA": "Panama",
            
            # Europe - Western
            "GB": "United Kingdom", 
            "DE": "Germany",
            "FR": "France",
            "IT": "Italy",
            "ES": "Spain",
            "NL": "Netherlands",
            "BE": "Belgium",
            "CH": "Switzerland",
            "AT": "Austria",
            "PT": "Portugal",
            "IE": "Ireland",
            "LU": "Luxembourg",
            
            # Europe - Nordic
            "SE": "Sweden",
            "NO": "Norway",
            "DK": "Denmark",
            "FI": "Finland",
            "IS": "Iceland",
            
            # Europe - Eastern
            "PL": "Poland",
            "CZ": "Czech Republic",
            "HU": "Hungary",
            "RO": "Romania",
            "BG": "Bulgaria",
            "GR": "Greece",
            "SK": "Slovakia",
            "SI": "Slovenia",
            "HR": "Croatia",
            "RS": "Serbia",
            "EE": "Estonia",
            "LV": "Latvia",
            "LT": "Lithuania",
            "RU": "Russia",
            "UA": "Ukraine",
            "BY": "Belarus",
            "KZ": "Kazakhstan",
            
            # Asia - East
            "CN": "China",
            "JP": "Japan",
            "KR": "South Korea",
            "TW": "Taiwan",
            "HK": "Hong Kong",
            "MO": "Macao",
            
            # Asia - Southeast
            "SG": "Singapore",
            "TH": "Thailand",
            "MY": "Malaysia",
            "ID": "Indonesia",
            "PH": "Philippines",
            "VN": "Vietnam",
            "MM": "Myanmar",
            "KH": "Cambodia",
            "LA": "Laos",
            "BN": "Brunei",
            
            # Asia - South
            "IN": "India",
            "PK": "Pakistan",
            "BD": "Bangladesh",
            "LK": "Sri Lanka",
            "NP": "Nepal",
            "BT": "Bhutan",
            "MV": "Maldives",
            
            # Asia - Central & West
            "TR": "Turkey",
            "IR": "Iran",
            "IQ": "Iraq",
            "AF": "Afghanistan",
            "UZ": "Uzbekistan",
            "TM": "Turkmenistan",
            "KG": "Kyrgyzstan",
            "TJ": "Tajikistan",
            
            # Middle East
            "AE": "United Arab Emirates",
            "SA": "Saudi Arabia",
            "IL": "Israel",
            "JO": "Jordan",
            "LB": "Lebanon",
            "SY": "Syria",
            "YE": "Yemen",
            "OM": "Oman",
            "QA": "Qatar",
            "BH": "Bahrain",
            "KW": "Kuwait",
            
            # Oceania
            "AU": "Australia",
            "NZ": "New Zealand",
            "FJ": "Fiji",
            "PG": "Papua New Guinea",
            
            # South America
            "BR": "Brazil",
            "AR": "Argentina",
            "CL": "Chile",
            "CO": "Colombia",
            "PE": "Peru",
            "VE": "Venezuela",
            "EC": "Ecuador",
            "BO": "Bolivia",
            "PY": "Paraguay",
            "UY": "Uruguay",
            "GY": "Guyana",
            "SR": "Suriname",
            
            # Africa - North
            "EG": "Egypt",
            "LY": "Libya",
            "TN": "Tunisia",
            "DZ": "Algeria",
            "MA": "Morocco",
            "SD": "Sudan",
            
            # Africa - West
            "NG": "Nigeria",
            "GH": "Ghana",
            "SN": "Senegal",
            "ML": "Mali",
            "BF": "Burkina Faso",
            "NE": "Niger",
            "CI": "Côte d'Ivoire",
            "LR": "Liberia",
            "SL": "Sierra Leone",
            "GN": "Guinea",
            "GM": "Gambia",
            
            # Africa - East
            "KE": "Kenya",
            "TZ": "Tanzania",
            "UG": "Uganda",
            "RW": "Rwanda",
            "BI": "Burundi",
            "ET": "Ethiopia",
            "SO": "Somalia",
            "DJ": "Djibouti",
            "ER": "Eritrea",
            
            # Africa - Southern
            "ZA": "South Africa",
            "ZW": "Zimbabwe",
            "BW": "Botswana",
            "NA": "Namibia",
            "ZM": "Zambia",
            "MW": "Malawi",
            "MZ": "Mozambique",
            "SZ": "Eswatini",
            "LS": "Lesotho",
            
            # Africa - Central
            "CD": "Democratic Republic of the Congo",
            "CG": "Republic of the Congo",
            "CM": "Cameroon",
            "CF": "Central African Republic",
            "TD": "Chad",
            "GA": "Gabon",
            "GQ": "Equatorial Guinea",
            "ST": "São Tomé and Príncipe",
            
            # Caribbean
            "JM": "Jamaica",
            "CU": "Cuba",
            "DO": "Dominican Republic",
            "HT": "Haiti",
            "TT": "Trinidad and Tobago",
            "BB": "Barbados",
            "BS": "Bahamas",
            "BZ": "Belize",
            
            # Additional European Countries
            "CY": "Cyprus",
            "MT": "Malta",
            "MK": "North Macedonia",
            "AL": "Albania",
            "ME": "Montenegro",
            "BA": "Bosnia and Herzegovina",
            "XK": "Kosovo",
            "MD": "Moldova",
            "AM": "Armenia",
            "AZ": "Azerbaijan",
            "GE": "Georgia",
            
            # Missing European Microstates
            "AD": "Andorra",
            "LI": "Liechtenstein",
            "MC": "Monaco",
            "SM": "San Marino",
            "VA": "Vatican City",
            
            # Missing Asian Countries
            "MN": "Mongolia",
            "KP": "North Korea",
            "TL": "Timor-Leste",
            
            # Missing African Countries
            "AO": "Angola",
            "BJ": "Benin",
            "CV": "Cape Verde",
            "KM": "Comoros",
            "MG": "Madagascar",
            "MR": "Mauritania",
            "MU": "Mauritius",
            "SC": "Seychelles",
            "TG": "Togo",
            
            # Missing Central American Countries
            "SV": "El Salvador",
            "HN": "Honduras",
            "NI": "Nicaragua",
            
            # Missing Caribbean Countries
            "AG": "Antigua and Barbuda",
            "DM": "Dominica",
            "GD": "Grenada",
            "KN": "Saint Kitts and Nevis",
            "LC": "Saint Lucia",
            "VC": "Saint Vincent and the Grenadines",
            "AW": "Aruba",
            "AI": "Anguilla",
            "VG": "British Virgin Islands",
            "KY": "Cayman Islands",
            "MS": "Montserrat",
            "TC": "Turks and Caicos Islands",
            "VI": "U.S. Virgin Islands",
            "PR": "Puerto Rico",
            "GP": "Guadeloupe",
            "MQ": "Martinique",
            
            # Missing Pacific Countries
            "WS": "Samoa",
            "TO": "Tonga",
            "VU": "Vanuatu",
            "SB": "Solomon Islands",
            "KI": "Kiribati",
            "NR": "Nauru",
            "TV": "Tuvalu",
            "PW": "Palau",
            "MH": "Marshall Islands",
            "FM": "Micronesia",
            "CK": "Cook Islands",
            "NU": "Niue",
            "AS": "American Samoa",
            "GU": "Guam",
            "MP": "Northern Mariana Islands",
            "NC": "New Caledonia",
            "PF": "French Polynesia",
            
            # Special Cases and Territories
            "PS": "Palestine",
            "EH": "Western Sahara",
            "SS": "South Sudan",
            "GL": "Greenland",
            "FO": "Faroe Islands",
            "GI": "Gibraltar",
            "JE": "Jersey",
            "GG": "Guernsey",
            "IM": "Isle of Man",
            "BM": "Bermuda",
            "FK": "Falkland Islands",
            "GF": "French Guiana"
        }
        
        return common_countries


# Utility functions for easy import
def convert_country_code_to_name(country_code: str) -> str:
    """
    Utility function to convert country code to name.
    
    Args:
        country_code: 2-letter ISO country code
        
    Returns:
        Full country name
    """
    return CountryService.get_country_name(country_code)


def validate_country_code(country_code: str) -> bool:
    """
    Utility function to validate country code.
    
    Args:
        country_code: 2-letter ISO country code
        
    Returns:
        True if valid, False otherwise
    """
    return CountryService.is_valid_country_code(country_code)
