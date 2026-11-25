using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.SignalR;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSignalR();
builder.Services.AddCors(options => options.AddDefaultPolicy(policy =>
    policy.WithOrigins("http://localhost:8000", "http://127.0.0.1:8000")
        .AllowAnyHeader()
        .AllowAnyMethod()
        .AllowCredentials()));
builder.Services.AddSingleton<OrderEventConsumer>();
builder.Services.AddHostedService<OrderEventConsumer>(provider =>
    provider.GetRequiredService<OrderEventConsumer>());

var app = builder.Build();
app.UseCors();
app.MapGet("/health", () => Results.Ok(new { status = "ok" }));
app.MapHub<NotificationHub>("/notifications");
app.Run();

public sealed class NotificationHub : Hub { }

public sealed class OrderEventConsumer : BackgroundService
{
    private readonly IHubContext<NotificationHub> _hub;
    private readonly string _connectionString;

    public OrderEventConsumer(IHubContext<NotificationHub> hub, IConfiguration configuration)
    {
        _hub = hub;
        _connectionString = configuration["RABBITMQ_URL"] ?? "amqp://orderapp:orderapp-dev@localhost/";
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            IConnection? connection = null;
            IModel? channel = null;

            try
            {
                var factory = new ConnectionFactory
                {
                    Uri = new Uri(_connectionString),
                    DispatchConsumersAsync = true
                };
                connection = factory.CreateConnection();
                channel = connection.CreateModel();
                channel.ExchangeDeclare("order.events", ExchangeType.Topic, durable: true);
                channel.QueueDeclare("notifications", durable: true, exclusive: false, autoDelete: false);
                channel.QueueBind("notifications", "order.events", "order.updated");
                channel.BasicQos(0, 1, false);

                var consumer = new AsyncEventingBasicConsumer(channel);
                consumer.Received += async (_, eventArgs) =>
                {
                    try
                    {
                        var json = Encoding.UTF8.GetString(eventArgs.Body.ToArray());
                        var order = JsonSerializer.Deserialize<JsonElement>(json);
                        await _hub.Clients.All.SendAsync("OrderUpdated", order, stoppingToken);
                        channel.BasicAck(eventArgs.DeliveryTag, multiple: false);
                    }
                    catch
                    {
                        channel.BasicNack(eventArgs.DeliveryTag, multiple: false, requeue: true);
                    }
                };

                channel.BasicConsume("notifications", autoAck: false, consumer);
                while (!stoppingToken.IsCancellationRequested && connection.IsOpen)
                {
                    await Task.Delay(TimeSpan.FromSeconds(1), stoppingToken);
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception error)
            {
                Console.WriteLine($"RabbitMQ chưa sẵn sàng: {error.Message}. Thử lại sau 3 giây...");
                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(3), stoppingToken);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
            finally
            {
                channel?.Dispose();
                connection?.Dispose();
            }
        }
    }
}