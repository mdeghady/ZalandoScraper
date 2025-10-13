# Zalando Product Scraper API

A high-performance FastAPI microservice that scrapes product data from Zalando fashion retail websites using both official APIs and web crawling techniques.

## 🚀 Features

- **Dual Scraping Strategy**: Combines official GraphQL API calls with web crawling for comprehensive data extraction
- **Multi-Domain Support**: Works across all Zalando regional domains (.it, .de, .fr, .es, .nl, .pl, .co.uk, .com)
- **Production Ready**: Built with FastAPI, includes error handling, rate limiting, and proper documentation
- **Real-time Data**: Fetches current pricing, availability, sizes, and stock information
- **Structured Responses**: Clean, normalized data models with Pydantic validation
- **Async Support**: High-performance asynchronous operations

## 🛠 Tech Stack

- **FastAPI** - Modern, fast web framework
- **Pydantic** - Data validation and settings management
- **Crawl4AI** - Advanced web crawling library
- **Requests** - HTTP client for API calls
- **Asyncio** - Asynchronous programming
- **Uvicorn** - ASGI server

## 📦 Installation

### Prerequisites
- Python 3.12+
- pip package manager

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/mdeghady/ZalandoScraper.git
cd zalando-scraper
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

The API will be available at `http://localhost:8001`

## 🐳 Docker Support

```bash
# Build the image
docker build -t zalando-scraper .

# Run the container
docker run -p 8001:8001 zalando-scraper
```

## 📚 API Documentation

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## 🔌 API Endpoints

### POST `/api/v1/scrape-product`

Scrapes product data from a Zalando URL.

**Request:**
```json
{
  "url": "https://www.zalando.it/acdc-calze-mehrfarbig-a9182f001-t11.html"
}
```

**Response Example:**
```json
{
  "success": true,
  "data": {
    "product_data": {
      "id": "ern:product::A9182F001-T11",
      "name": "5ER PACK AC/DC ROCKBAND - Calze - mehrfarbig",
      "sku": "A9182F001-T11",
      "brand": "AC/DC",
      "model_number": null,
      "gtin": "4025055469851",
      "display_price": {
        "trackingCurrentAmount": 27.95,
        "trackingDiscountAmount": null,
        "promotional": null,
        "original": {
          "amount": 27.95,
          "currency": "EUR"
        },
        "displayMode": "BLACK_PRICE"
      },
      "packshot_image": "https://img01.ztat.net/article/spp-media-p1/14a4d456fad04eea8a37abd61fb2ff30/e4598dee89594a079a71a1a25864b897.jpg?imwidth=300&filter=packshot",
      "silhouette": "STOCKING",
      "navigation_target_group": "MEN",
      "simples": [
        {
          "size": "41-46",
          "sku": "A9182F001-T110416000"
        }
      ]
    },
    "sku_data": {
      "sku": "A9182F001-T11",
      "model_number": null,
      "gtin": "4025055469851",
      "simples": [
        {
          "sku": "A9182F001-T110416000",
          "gtins": ["4025055469851"],
          "offer": {
            "manufacturerDetails": null,
            "merchant": {
              "id": "5d0b1d51-04c8-414f-a29c-f2bc1ed26247"
            }
          }
        }
      ]
    },
    "crawl_data": {
      "available_sizes": [
        {
          "size": "M",
          "price": "87,90 €",
          "availability": "out_of_stock",
          "stock_quantity": null,
          "sku": null
        },
        {
          "size": "L", 
          "price": "87,90 €",
          "availability": "in_stock",
          "stock_quantity": 2,
          "sku": null
        },
        {
          "size": "XL",
          "price": "80,50 €", 
          "availability": "low_stock",
          "stock_quantity": 1,
          "sku": null
        }
      ],
      "product_highlight": "Questo è uno degli articoli più popolari del mese",
      "url": "https://www.zalando.it/acdc-calze-mehrfarbig-a9182f001-t11.html"
    },
    "metadata": {
      "domain": "zalando.it",
      "language": "en-US",
      "data_sources": ["api", "crawl"],
      "merged_at": "2024-01-01T00:00:00Z"
    }
  },
  "metadata": {
    "product_code": "A9182F001-T11",
    "domain": "zalando.it",
    "language": "en-US",
    "sources_used": {
      "api": true,
      "crawl": true
    }
  },
  "error": null
}
```

### GET `/api/v1/health`

Health check endpoint to verify service status.

**Response:**
```json
{
  "status": "healthy",
  "service": "Zalando Scraper API"
}
```

### GET `/`

Root endpoint with service information.

## 🏗 Project Structure

```
zalandoScraper/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   └── v1/
│   │       └── endpoints.py    # API route handlers
│   ├── core/
│   │   └── config.py           # Application configuration
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   ├── services/
│   │   ├── scraper_service.py  # Main orchestration service
│   │   ├── api_scraper.py      # Zalando API client
│   │   └── crawl_scraper.py    # Web crawling service
│   └── utils/
│       └── url_parser.py       # URL parsing utilities
├── requirements.txt
├── Dockerfile
└── README.md
```

## 🔧 Configuration

Environment variables (via `.env` file):

```env
DEBUG=false
CORS_ORIGINS=["*"]
RATE_LIMIT_PER_MINUTE=60
```

## 🎯 Usage Examples

### Python Client
```python
import requests

api_url = "http://localhost:8000/api/v1/scrape-product"
payload = {
    "url": "https://www.zalando.it/acdc-calze-mehrfarbig-a9182f001-t11.html"
}

response = requests.post(api_url, json=payload)
data = response.json()

if data["success"]:
    product = data["data"]["product_data"]
    print(f"Product: {product['name']}")
    print(f"Brand: {product['brand']}")
    print(f"Price: {product['display_price']['trackingCurrentAmount']} {product['display_price']['original']['currency']}")
```

### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/scrape-product" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.zalando.it/acdc-calze-mehrfarbig-a9182f001-t11.html"}'
```

## ⚠️ Important Notes

- **Rate Limiting**: The service includes built-in rate limiting to prevent abuse
- **Error Handling**: Comprehensive error handling for network issues, parsing errors, and invalid URLs
- **Data Normalization**: Prices are automatically normalized (divided by 100 when necessary)
- **Size Filtering**: Duplicate sizes and invalid entries are automatically filtered out
- **Availability Detection**: Stock status is automatically detected and normalized

## 🚨 Legal Disclaimer

This project is for educational and development purposes only. Ensure you comply with:
- Zalando's Terms of Service
- robots.txt directives
- Rate limiting guidelines
- Applicable web scraping laws in your jurisdiction

Users are responsible for ensuring their usage complies with all applicable laws and terms of service.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
1. Check the API documentation at `/docs`
2. Review the code examples above
3. Open an issue in the repository

---

**Note**: This service is designed for legitimate use cases and respects Zalando's infrastructure through proper rate limiting and error handling.
