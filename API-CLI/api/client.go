package api

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)


////////////////////
//   Structures   //
////////////////////
type Client struct {
	BaseURL    string
	HTTPClient *http.Client
	AuthToken  string
}


/////////////////////
//   Constructor   //
/////////////////////
func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 15 * time.Second,
		},
	}
}


////////////////////////
//  Helper Functions  //
////////////////////////
func (c *Client) setAuth(req *http.Request) {
	if c.AuthToken != "" {
		req.Header.Set("Authorization", "Bearer "+c.AuthToken)
	}
}

func (c *Client) doRequest(req *http.Request) ([]byte, error) {
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		var apiErr map[string]interface{}
		if err := json.Unmarshal(respBody, &apiErr); err == nil {
			if msg, ok := apiErr["error"].(string); ok {
				return nil, fmt.Errorf("API error %s: %s", resp.Status, msg)
			}
			if msg, ok := apiErr["message"].(string); ok {
				return nil, fmt.Errorf("API error %s: %s", resp.Status, msg)
			}
		}
		return nil, fmt.Errorf("API error %s: %s", resp.Status, string(respBody))
	}

	return respBody, nil
}


////////////////////////
//  Public Functions  //
////////////////////////
func (c *Client) Post(ctx context.Context, endpoint string, fileName string, user string, targetColumn string) ([]byte, error) {
	payload := map[string]string{"user": user, "fileName": fileName}
	if targetColumn != "" {
		payload["targetColumn"] = targetColumn
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+endpoint, bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	c.setAuth(req)

	return c.doRequest(req)
}

func (c *Client) PostJSON(ctx context.Context, endpoint string, payload map[string]interface{}) ([]byte, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+endpoint, bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	c.setAuth(req)
	return c.doRequest(req)
}

func (c *Client) Get(ctx context.Context, endpoint string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+endpoint, nil)
	if err != nil {
		return nil, err
	}
	c.setAuth(req)

	return c.doRequest(req)
}

func (c *Client) Put(ctx context.Context, endpoint string, fileName string, user string, body []byte) error {
	u, err := url.Parse(c.BaseURL + endpoint)
	if err != nil {
		return err
	}
	q := u.Query()
	q.Set("fileName", fileName)
	q.Set("userName", user)
	u.RawQuery = q.Encode()

	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewBuffer(body)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPut, u.String(), bodyReader)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "text/csv")
	c.setAuth(req)

	_, err = c.doRequest(req)
	return err
}

func (c *Client) Delete(ctx context.Context, endpoint string, userName string, datasetName string) error {
	u, err := url.Parse(c.BaseURL + endpoint)
	if err != nil {
		return err
	}
	q := u.Query()
	q.Set("userName", userName)
	q.Set("datasetName", datasetName)
	u.RawQuery = q.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, u.String(), nil)
	if err != nil {
		return fmt.Errorf("error creating request: %w", err)
	}
	c.setAuth(req)

	_, err = c.doRequest(req)
	return err
}
