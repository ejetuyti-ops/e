using System.Diagnostics;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.WinForms;

namespace EJET.Browser;

public sealed class BrowserForm : Form
{
    private const string Api = "http://127.0.0.1:8765";
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(8) };
    private readonly TextBox _address = new();
    private readonly WebView2 _web = new();
    private readonly Label _status = new();
    private Process? _python;
    private bool _ownsServer;

    public BrowserForm()
    {
        Text = "EJET Browser";
        MinimumSize = new Size(900, 600);
        Size = new Size(1280, 820);
        BackColor = Color.FromArgb(9, 9, 9);
        ForeColor = Color.FromArgb(230, 230, 230);
        BuildChrome();
        Shown += async (_, _) => await StartAsync();
        FormClosing += (_, _) => StopServer();
    }

    private void BuildChrome()
    {
        var top = new Panel { Dock = DockStyle.Top, Height = 62, BackColor = Color.FromArgb(17, 17, 17), Padding = new Padding(10) };
        var row = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false, BackColor = Color.Transparent };
        top.Controls.Add(row);
        AddButton(row, "‹", "رجوع", (_, _) => { if (_web.CanGoBack) _web.GoBack(); });
        AddButton(row, "›", "تقدم", (_, _) => { if (_web.CanGoForward) _web.GoForward(); });
        AddButton(row, "⟳", "تحديث", (_, _) => _web.Reload());
        AddButton(row, "⌂", "الرئيسية", (_, _) => ShowHome());
        _address.Width = 690;
        _address.Height = 36;
        _address.Margin = new Padding(8, 5, 8, 4);
        _address.BackColor = Color.FromArgb(29, 29, 29);
        _address.ForeColor = Color.White;
        _address.BorderStyle = BorderStyle.FixedSingle;
        _address.Font = new Font("Segoe UI", 11);
        _address.PlaceholderText = "ابحث في EJET أو اكتب عنوان موقع...";
        _address.KeyDown += async (_, e) => { if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; await NavigateInputAsync(); } };
        row.Controls.Add(_address);
        AddButton(row, "بحث / فتح", "بحث أو فتح رابط", async (_, _) => await NavigateInputAsync(), 112);
        _web.Dock = DockStyle.Fill;
        _web.DefaultBackgroundColor = Color.FromArgb(9, 9, 9);
        _status.Dock = DockStyle.Bottom;
        _status.Height = 25;
        _status.Padding = new Padding(12, 4, 0, 0);
        _status.BackColor = Color.FromArgb(17, 17, 17);
        _status.ForeColor = Color.Silver;
        Controls.Add(_web);
        Controls.Add(_status);
        Controls.Add(top);
    }

    private static void AddButton(Control parent, string label, string tip, EventHandler click, int width = 42)
    {
        var b = new Button { Text = label, Width = width, Height = 36, Margin = new Padding(3, 3, 3, 3), FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(35, 35, 35), ForeColor = Color.Gainsboro, Font = new Font("Segoe UI", 10, FontStyle.Bold), UseVisualStyleBackColor = false };
        b.FlatAppearance.BorderColor = Color.FromArgb(65, 65, 65);
        b.FlatAppearance.MouseOverBackColor = Color.FromArgb(55, 55, 55);
        new ToolTip().SetToolTip(b, tip);
        b.Click += click;
        parent.Controls.Add(b);
    }

    private async Task StartAsync()
    {
        try
        {
            var script = Path.Combine(AppContext.BaseDirectory, "search_server.py");
            if (File.Exists(script))
            {
                try
                {
                    using var response = await _http.GetAsync(Api + "/api/health");
                }
                catch
                {
                    var psi = new ProcessStartInfo("python", $"\"{script}\"") { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = AppContext.BaseDirectory };
                    _python = Process.Start(psi);
                    _ownsServer = _python is not null;
                }
            }
            for (var i = 0; i < 30; i++)
            {
                try
                {
                    using var response = await _http.GetAsync(Api + "/api/health");
                    if (response.IsSuccessStatusCode) break;
                }
                catch { await Task.Delay(300); }
            }
            await _web.EnsureCoreWebView2Async();
            _web.CoreWebView2.NavigationCompleted += (_, _) => { if (_web.Source is not null) _address.Text = _web.Source.ToString(); };
            ShowHome();
            _status.Text = "EJET Search جاهز — قاعدة البيانات محلية ومحفوظة";
        }
        catch (Exception ex) { _status.Text = "تعذر تشغيل المتصفح: " + ex.Message; }
    }

    private void ShowHome()
    {
        _address.Text = "";
        _web.NavigateToString(Page("EJET", "<p class='muted'>ابحث في الصفحات التي فهرستها EJET Search، أو اكتب رابط موقع لفتحه مباشرة.</p>", true));
    }

    private async Task NavigateInputAsync()
    {
        var value = _address.Text.Trim();
        if (string.IsNullOrWhiteSpace(value)) return;
        if (Uri.TryCreate(value, UriKind.Absolute, out var uri) && (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
        {
            _web.CoreWebView2?.Navigate(uri.ToString());
            return;
        }
        if (!value.Contains(' ') && value.Contains('.') && !value.StartsWith("www.", StringComparison.OrdinalIgnoreCase))
        {
            _web.CoreWebView2?.Navigate("https://" + value);
            return;
        }
        await SearchAsync(value);
    }

    private async Task SearchAsync(string query)
    {
        try
        {
            _status.Text = "جاري البحث...";
            var url = Api + "/api/search?q=" + Uri.EscapeDataString(query);
            using var response = await _http.GetAsync(url);
            response.EnsureSuccessStatusCode();
            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            var results = doc.RootElement.GetProperty("results");
            var cards = new StringBuilder();
            foreach (var item in results.EnumerateArray())
            {
                var title = item.GetProperty("title").GetString() ?? "بدون عنوان";
                var link = item.GetProperty("url").GetString() ?? "";
                var excerpt = item.GetProperty("excerpt").GetString() ?? "";
                cards.Append("<article><a href='").Append(WebUtility.HtmlEncode(link)).Append("'>")
                    .Append(WebUtility.HtmlEncode(title)).Append("</a><div class='url'>")
                    .Append(WebUtility.HtmlEncode(link)).Append("</div><p>")
                    .Append(WebUtility.HtmlEncode(excerpt)).Append("</p></article>");
            }
            var body = cards.Length == 0 ? "<p class='muted'>لا توجد نتائج مفهرسة لهذه العبارة. أضف موقعاً إلى الفهرسة ثم أعد البحث.</p>" : cards.ToString();
            _web.NavigateToString(Page("نتائج البحث: " + query, body, false));
            _status.Text = results.GetArrayLength() + " نتيجة";
        }
        catch (Exception ex) { _status.Text = "محرك البحث غير متاح: " + ex.Message; }
    }

    private static string Page(string title, string body, bool home) => $@"<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><title>{WebUtility.HtmlEncode(title)}</title><style>
        *{{box-sizing:border-box}}body{{margin:0;background:#090909;color:#eee;font:16px Segoe UI,Arial;padding:48px 7%}}
        h1{{font-size:48px;letter-spacing:2px;color:#f1f1f1;margin:0 0 12px}}.muted{{color:#aaa;line-height:1.9}}
        main{{max-width:900px;margin:{(home ? "90px auto" : "20px auto")};}}article{{padding:20px 0;border-bottom:1px solid #303030}}
        a{{color:#eee;font-size:21px;text-decoration:none}}a:hover{{text-decoration:underline;color:white}}
        .url{{direction:ltr;text-align:right;color:#999;font-size:13px;margin-top:7px}}article p{{color:#bbb;line-height:1.8}}
        .tag{{color:#888;font-size:12px;letter-spacing:4px;margin-bottom:14px}}
        </style></head><body><main><div class='tag'>PRIVATE • LOCAL SEARCH</div><h1>EJET</h1>{body}</main></body></html>";

    private void StopServer()
    {
        try { if (_ownsServer && _python is { HasExited: false }) _python.Kill(true); } catch { }
        _http.Dispose();
    }
}